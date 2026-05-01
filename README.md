# Highwatch AI - Google Drive RAG System

A retrieval-augmented generation system that connects to Google Drive, processes documents, and provides grounded AI answers using Groq (Llama 3.3).

## Key Endpoints
- / : Main Dashboard (Chat Interface)
- /docs : Interactive API Documentation (Swagger)
- /api/v1/sync-drive : Sync files from Google Drive
- /api/v1/ask : Ask questions against the knowledge base

## Features
- Google Drive Integration: Automated fetching of PDFs, Google Docs, and TXT files.
- Document Processing: Semantic chunking and high-performance embeddings using FastEmbed.
- Vector Search: Efficient similarity search powered by FAISS.
- Groq Integration: State-of-the-art LLM answers grounded in your specific documents.

## Local Setup

1. Install dependencies:
   pip install -r requirements.txt

2. Configure environment:
   Create a .env file with the following:
   GROQ_API_KEY=your_key
   LLM_PROVIDER=groq
   GOOGLE_DRIVE_FOLDER_IDS=your_folder_id

3. Run the application:
   python main.py

## Deployment (Render)

This project is optimized for deployment on Render's free tier.

1. Set the following environment variables in Render:
   - GROQ_API_KEY
   - LLM_PROVIDER=groq
   - GOOGLE_CREDENTIALS_JSON (Content of your credentials.json)
   - GOOGLE_TOKEN_JSON (Content of your generated token.json)

2. The application will automatically use the Dockerfile for building.
