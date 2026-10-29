from io import BytesIO
import fitz
import pytest
from document_processor import extract_document, chunk_document
from retrieval import Retriever
from llm import LocalLLM

def make_pdf():
    doc = fitz.open()
    for text in ['The study evaluates solar panels in schools. The main finding is a 20 percent reduction in electricity use.', 'The authors caution that the sample covered only three schools and recommend longer follow-up.']:
        page = doc.new_page(); page.insert_text((72, 72), text)
    data = doc.tobytes(); doc.close(); return data

def test_extracts_pages_and_text():
    d = extract_document(make_pdf(), 'study.pdf')
    assert d.total_pages == 2 and d.pages[0].page_number == 1
    assert 'solar panels' in d.pages[0].text

def test_rejects_wrong_type_and_empty():
    with pytest.raises(ValueError): extract_document(b'abc', 'notes.txt')
    with pytest.raises(ValueError): extract_document(b'', 'empty.pdf')

def test_chunks_preserve_page_metadata():
    chunks = chunk_document(extract_document(make_pdf(), 'study.pdf'), chunk_size=80, overlap=10)
    assert chunks and {c.page_number for c in chunks} == {1, 2}

def test_retrieval_finds_relevant_passage_and_page():
    r = Retriever(chunk_document(extract_document(make_pdf(), 'study.pdf')))
    result = r.search('How much electricity use was reduced?')[0]
    assert result.page_number == 1 and '20 percent' in result.text

def test_unsupported_question_is_transparent():
    r = Retriever(chunk_document(extract_document(make_pdf(), 'study.pdf')))
    answer = LocalLLM().answer('Who won the election on Mars?', r.search('Who won the election on Mars?'))
    assert 'enough evidence' in answer.lower()
