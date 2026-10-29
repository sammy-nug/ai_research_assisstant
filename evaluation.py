"""Small, repeatable evaluation for extraction, retrieval, citations, and safe refusal."""
from __future__ import annotations
from pathlib import Path
import fitz
from document_processor import extract_document, chunk_document
from retrieval import Retriever
from llm import LocalLLM

SAMPLE_PAGES = [
    'Solar Learning Study.\n\nThis study evaluates solar panels in schools.\nThe main finding is a 20 percent reduction in electricity use.',
    'Methods and limitations.\n\nThe sample covered three schools.\nThe authors recommend longer follow-up and caution against generalizing beyond similar schools.',
]
# Ten questions with expected evidence terms and expected source page.
QUESTIONS = [
    ('What is the main topic?', ['solar panels'], 1),
    ('What did the study evaluate?', ['solar panels'], 1),
    ('What was the main finding?', ['20 percent'], 1),
    ('How much was electricity use reduced?', ['20 percent'], 1),
    ('How many schools were in the sample?', ['three schools'], 2),
    ('What limitation is stated?', ['generalizing'], 2),
    ('What do the authors recommend?', ['longer follow-up'], 2),
    ('What should readers be cautious about?', ['generalizing'], 2),
    ('What evidence supports the conclusion?', ['20 percent reduction'], 1),
]

def build_sample_pdf(path: Path) -> None:
    doc = fitz.open()
    for text in SAMPLE_PAGES:
        page = doc.new_page(); page.insert_textbox(fitz.Rect(72, 72, 540, 700), text, fontsize=12, lineheight=1.4)
    doc.save(path); doc.close()

def run() -> int:
    path = Path('/tmp/ai_research_assistant_sample.pdf')
    build_sample_pdf(path)
    document = extract_document(path.read_bytes(), path.name)
    retriever = Retriever(chunk_document(document))
    llm = LocalLLM()
    passed = 0
    for question, expected_terms, expected_page in QUESTIONS:
        results = retriever.search(question)
        evidence = ' '.join(r.text.lower() for r in results)
        ok = all(term.lower() in evidence for term in expected_terms) and any(r.page_number == expected_page for r in results)
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} | {question} | cited_pages={[r.page_number for r in results]}")
    refusal = llm.answer('Who won the election on Mars?', retriever.search('Who won the election on Mars?'))
    safe = 'enough evidence' in refusal.lower()
    passed += int(safe)
    print(f"{'PASS' if safe else 'FAIL'} | unsupported question refusal")
    total = len(QUESTIONS) + 1
    print(f'\nEvaluation: {passed}/{total} checks passed.')
    return 0 if passed == total else 1

if __name__ == '__main__':
    raise SystemExit(run())
