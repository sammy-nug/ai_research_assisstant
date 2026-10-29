from __future__ import annotations
import streamlit as st
from document_processor import extract_document, chunk_document
from retrieval import Retriever
from llm import LocalLLM

st.set_page_config(page_title='AI Research Assistant', page_icon='📚', layout='wide')
st.markdown('''<style>.block-container{max-width:1100px;padding-top:2rem}.source{border-left:3px solid #4f46e5;padding:.5rem 1rem;background:#f8fafc;border-radius:0 8px 8px 0;margin:.4rem 0}</style>''', unsafe_allow_html=True)

if 'document' not in st.session_state: st.session_state.document = None
if 'retriever' not in st.session_state: st.session_state.retriever = None
if 'chunks' not in st.session_state: st.session_state.chunks = []
if 'history' not in st.session_state: st.session_state.history = []
if 'llm' not in st.session_state: st.session_state.llm = LocalLLM()

with st.sidebar:
    st.title('AI Research Assistant')
    st.caption('Private, local-first document understanding')
    st.markdown('Upload one readable PDF, retrieve evidence, and ask grounded questions.')
    uploaded = st.file_uploader('Upload a PDF', type=['pdf'], help='Maximum 25 MB and 500 pages.')
    if st.button('Start new document session', use_container_width=True):
        for key in ('document','retriever','chunks'): st.session_state[key] = None if key != 'chunks' else []
        st.session_state.history = []; st.rerun()
    if st.session_state.document:
        d = st.session_state.document
        st.success(f'{d.name}\n\n{d.total_pages} pages · {d.characters:,} characters')
        st.caption(f'Retrieval: {st.session_state.retriever.mode}')
        st.caption(st.session_state.llm.last_status)

st.title('Understand your research documents faster')
st.write('Generate a transparent summary and ask questions with page-level supporting evidence. Documents and chat history remain in this session only.')

if uploaded is not None and (not st.session_state.document or st.session_state.document.name != uploaded.name):
    with st.spinner('Extracting text and building the retrieval index…'):
        try:
            document = extract_document(uploaded.getvalue(), uploaded.name)
            chunks = chunk_document(document)
            st.session_state.document, st.session_state.chunks = document, chunks
            st.session_state.retriever = Retriever(chunks)
            st.session_state.history = []
            st.success(f'Processed {document.total_pages} pages into {len(chunks)} searchable chunks.')
        except ValueError as exc: st.error(str(exc))

if not st.session_state.document:
    st.info('Upload a PDF from the sidebar to begin. Scanned PDFs need OCR before they can be searched.')
else:
    document, retriever, llm = st.session_state.document, st.session_state.retriever, st.session_state.llm
    tab_summary, tab_chat, tab_details = st.tabs(['Summary', 'Ask questions', 'Document details'])
    with tab_summary:
        col1, col2 = st.columns([1, 3])
        with col1: detailed = st.toggle('Detailed summary', value=False)
        with col2:
            if st.button('Generate summary', type='primary'):
                with st.spinner('Generating a grounded summary…'):
                    st.session_state.summary = llm.summarize(st.session_state.chunks, detailed)
        if st.session_state.get('summary'): st.markdown(st.session_state.summary)
        else: st.caption('Choose a summary style and click Generate summary.')
    with tab_chat:
        for item in st.session_state.history:
            with st.chat_message(item['role']): st.markdown(item['content'])
            if item.get('sources'):
                for source in item['sources']:
                    st.markdown(f"<div class='source'><b>{source.source}</b> · page {source.page_number}<br>{source.text[:500]}…</div>", unsafe_allow_html=True)
        question = st.chat_input('Ask a question about this document…')
        if question:
            st.session_state.history.append({'role':'user','content':question})
            results = retriever.search(question, k=4)
            with st.spinner('Searching the document and drafting an answer…'): answer = llm.answer(question, results)
            st.session_state.history.append({'role':'assistant','content':answer,'sources':results})
            st.rerun()
        if st.button('Clear conversation'): st.session_state.history = []; st.rerun()
    with tab_details:
        st.metric('Pages', document.total_pages); st.metric('Extracted characters', f'{document.characters:,}')
        st.write('The application does not upload documents to a hosted AI service. Ollama, when available, runs on your machine. Without Ollama or embedding packages, a deterministic lexical retrieval and extractive answer fallback is used.')
