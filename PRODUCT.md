# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: recruiters and interviewers reviewing Highwatch RAG as a portfolio project. They usually open it for a few minutes, upload a document or two (or look at what is already indexed), ask a couple of questions, and judge whether the answers are grounded and the engineering is careful.

Secondary: the author, using it on their own documents.

## Product Purpose

Highwatch RAG answers questions using only the documents a person gives it (uploads or a Google Drive folder). Every answer cites the exact excerpts it used, and when the documents do not contain the answer it says so instead of guessing. Success for a reviewer: within one or two questions they see a correct answer, can open the cited passage, and see an honest "not in your documents" reply for an off-topic question.

## Positioning

Grounded answers with verifiable, numbered citations (file, page, section, relevance score) and an explicit refusal when the documents do not cover the question. Runs at $0: local embeddings (FastEmbed, BAAI/bge-small-en-v1.5), FAISS on disk, free Groq or Gemini models, or a no-LLM extractive mode.

## Operating Context

- Documents are mixed: often policies and handbooks (refunds, HR, compliance), but any PDF, DOCX, TXT or Markdown file.
- Ingestion: drag-and-drop upload (max size set by the server, 10 MB by default) and Google Drive folder sync.
- Typical session: upload, wait for indexing, ask, expand citations, maybe delete or re-sync.
- Runs locally (Python or Docker) or on a free host; a reviewer may hit a cold start.

## Capabilities and Constraints

- Answer statuses: answered, extractive (no LLM), insufficient_context, no_documents, llm_error (shows a warning plus extractive excerpts).
- Citations: number, file name, page or page range, section heading, relevance score, snippet, Drive link for Drive files.
- Documents: status (processing, indexed, failed with error), chunk count, page count, source (upload or Drive). Duplicate uploads are rejected.
- Health: readiness endpoint reports storage, index, registry, LLM, embedding model and Drive status.
- Optional API key (prompted in the browser on 401).
- LLM provider and model are shown from server config; "extractive" means no LLM.
- Frontend is vanilla HTML, CSS and JavaScript served by FastAPI at `/` and `/static`; no build step.
- Strict $0 budget: no paid services, fonts or assets that need a paid license.

## Brand Commitments

- Name: "Highwatch RAG".
- No AI-assistant or tool attribution anywhere in the repository (files, commits or pull requests).

## Evidence on Hand

- No logo, screenshots, testimonials or usage numbers exist. Do not invent users, customers, accuracy figures or benchmarks.
- Real demo material must come from documents the user uploads.

## Product Principles

1. Show the evidence: every claim in an answer traces to a visible excerpt.
2. Say "I don't know" plainly; a refusal is a feature, not an error.
3. Make system state legible: indexing, failures, duplicates and the active model are always visible.
4. A first-time reviewer should succeed in under a minute without reading docs.
