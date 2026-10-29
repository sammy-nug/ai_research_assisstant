# AI Research Assistant for Students and Professionals

A local-first Streamlit application for understanding PDF documents. Upload a readable PDF, generate a concise or detailed summary, ask questions, and inspect the supporting passages and page numbers.

## Why this project

Long reports and papers are difficult to search manually. This app uses a simple retrieval-augmented generation (RAG) pipeline so answers are grounded in passages from the uploaded document. It is designed for students, researchers, professionals, and self-learners.

## Features

- PDF validation, page-aware text extraction, size/page limits, and scanned-PDF guidance.
- Overlapping chunks retain document name and page metadata.
- Optional ChromaDB plus `all-MiniLM-L6-v2` semantic retrieval.
- Deterministic lexical retrieval fallback, so the app remains testable without model downloads.
- Local Ollama/Llama summarization and question answering when Ollama is running.
- Extractive fallback summary/answer when Ollama is not available; no simulated or invented citations.
- Chat history, clear conversation, new-session controls, and visible source excerpts.

## Architecture

`app.py` contains the UI. `document_processor.py` validates PDFs and creates page-aware chunks. `retrieval.py` indexes and retrieves chunks. `llm.py` calls Ollama or uses a transparent local fallback. `prompts.py` keeps grounding rules reusable. `tests/` checks extraction, retrieval, citations, errors, and unsupported questions.

## Prerequisites

Ubuntu/Linux, Python 3.10+, and optionally [Ollama](https://ollama.com/). Local LLMs need sufficient RAM, CPU/GPU capacity, and disk space. A small 3B model is a practical starting point; larger models improve quality but require more resources.

## Install and run

```bash
cd ai-research-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

The app opens at `http://localhost:8501`. Upload a selectable-text PDF. Uploaded files are processed in memory and are not sent to a hosted AI service.

### Enable local Llama answers

Install Ollama from its official site, then:

```bash
ollama serve
ollama pull llama3.2:3b
```

Set `OLLAMA_MODEL` in `.env` to another locally installed compatible model if desired. If Ollama is unavailable, the app clearly labels fallback mode and still provides extraction, retrieval, citations, and extractive responses.

### Optional semantic retrieval

The default install is intentionally lightweight. For vector similarity retrieval, uncomment the ChromaDB and sentence-transformers lines in `requirements.txt`, reinstall, and allow the embedding model to download once. The app falls back automatically if those packages or downloads are unavailable.

## Test and evaluate

```bash
pytest -q
```

The automated suite creates a two-page sample PDF and tests: text/page extraction; invalid and empty files; chunk page metadata; relevant retrieval and page citation; and refusal of an unsupported question. These are component tests, not a claim that an LLM is factually correct. For manual evaluation, ask at least these 10 questions against a known sample document and compare the response with the cited page: (1) What is the main topic? (2) What is the research question? (3) What method was used? (4) What is the sample size? (5) What is the main finding? (6) What limitation is stated? (7) What recommendation is made? (8) What date or timeframe is mentioned? (9) What evidence supports the conclusion? (10) Ask for a fact absent from the document and verify that the app admits insufficient evidence.

## Troubleshooting

- **No selectable text:** OCR the PDF with a tool such as `ocrmypdf`, then upload the OCR output.
- **Ollama unavailable:** confirm `ollama serve`, `curl http://localhost:11434/api/tags`, and the model name in `.env`.
- **Slow first run:** embedding models download once and local LLM inference depends on hardware.
- **Memory pressure:** use `llama3.2:3b`, process shorter documents, or leave optional embeddings disabled.

## Privacy, cost, and limitations

The core workflow is free and local. No API keys are required. The app does not persist uploads after the session by design, but Streamlit session state lasts for the current process. Scanned PDFs need OCR; tables, figures, and complex layouts may extract imperfectly; fallback responses are not a substitute for a local LLM; and even a local LLM can make mistakes, so check the cited passages.

## GitHub

Before publishing, review `.env` and ensure it contains no secrets. Then:

```bash
git init
git add .
git commit -m "Build local AI research assistant"
git branch -M main
git remote add origin https://github.com/YOUR-USER/ai-research-assistant.git
git push -u origin main
```

## Future improvements

Multi-document comparison, OCR integration, table-aware extraction, persistent opt-in indexes, streaming responses, evaluation scoring, and an explicit model availability health check are natural next steps.
