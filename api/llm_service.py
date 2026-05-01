"""
LLM Answer Service
Generates answers grounded in retrieved document context using OpenAI or Gemini.
"""

from typing import Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# System prompt for the RAG pipeline
SYSTEM_PROMPT = """You are an intelligent document assistant for Highwatch AI. Your role is to answer user questions accurately based ONLY on the provided document context.

Rules:
1. Answer ONLY from the provided context. Do not use external knowledge.
2. If the context doesn't contain enough information to answer fully, say so clearly.
3. Be concise but thorough. Use bullet points for lists.
4. Always cite which document(s) your answer comes from.
5. If multiple documents contain relevant information, synthesize them into a coherent answer.
6. Maintain a professional, helpful tone.
7. If the question is ambiguous, provide the most likely interpretation and answer.
"""


def build_context_prompt(query: str, chunks: list[dict]) -> str:
    """Build the prompt with retrieved context chunks."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        file_name = chunk.get("file_name", "Unknown")
        text = chunk.get("text", "")
        score = chunk.get("score", 0)
        context_parts.append(
            f"[Document {i}: {file_name} (relevance: {score:.2f})]\n{text}"
        )

    context = "\n\n---\n\n".join(context_parts)

    return f"""Based on the following document excerpts, answer the user's question.

DOCUMENT CONTEXT:
{context}

USER QUESTION: {query}

Provide a clear, accurate answer based on the documents above. Cite the source documents."""


class LLMService:
    """LLM service for generating answers from context."""

    def __init__(self):
        self.settings = get_settings()
        self._openai_client = None
        self._gemini_model = None

    async def generate_answer(
        self,
        query: str,
        context_chunks: list[dict],
        provider: Optional[str] = None,
    ) -> str:
        """
        Generate an answer using the LLM with retrieved context.
        
        Args:
            query: User's question.
            context_chunks: Retrieved document chunks with metadata.
            provider: LLM provider override ("openai" or "gemini").
            
        Returns:
            Generated answer string.
        """
        provider = provider or self.settings.llm_provider

        if not context_chunks:
            return (
                "I couldn't find any relevant information in the knowledge base to answer your question. "
                "Please try rephrasing your question or ensure the relevant documents have been synced."
            )

        prompt = build_context_prompt(query, context_chunks)

        try:
            if provider == "openai":
                return await self._generate_openai(prompt)
            elif provider == "gemini":
                return await self._generate_gemini(prompt)
            elif provider == "groq":
                return await self._generate_groq(prompt)
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
        except Exception as e:
            logger.error("LLM generation failed", provider=provider, error=str(e))
            # Fallback: return a formatted context-based answer
            return self._fallback_answer(query, context_chunks)

    async def _generate_openai(self, prompt: str) -> str:
        """Generate answer using OpenAI API."""
        if self._openai_client is None:
            from openai import AsyncOpenAI
            
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self._openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)

        response = await self._openai_client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        return response.choices[0].message.content

    async def _generate_gemini(self, prompt: str) -> str:
        """Generate answer using Google Gemini API."""
        if self._gemini_model is None:
            import google.generativeai as genai
            
            if not self.settings.gemini_api_key:
                raise ValueError("GEMINI_API_KEY not configured")
            genai.configure(api_key=self.settings.gemini_api_key)
            self._gemini_model = genai.GenerativeModel(
                model_name=self.settings.gemini_model,
                system_instruction=SYSTEM_PROMPT,
            )

        response = await self._gemini_model.generate_content_async(
            prompt,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 1500,
            },
        )
        return response.text

    async def _generate_groq(self, prompt: str) -> str:
        """Generate answer using Groq API."""
        from groq import AsyncGroq
        
        if not self.settings.groq_api_key:
            raise ValueError("GROQ_API_KEY not configured")
            
        client = AsyncGroq(api_key=self.settings.groq_api_key)
        
        response = await client.chat.completions.create(
            model=self.settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        return response.choices[0].message.content

    def _fallback_answer(self, query: str, chunks: list[dict]) -> str:
        """Provide a basic answer from context when LLM fails."""
        sources = list(set(c.get("file_name", "Unknown") for c in chunks))
        context_text = "\n\n".join(
            f"From {c.get('file_name', 'Unknown')}:\n{c.get('text', '')}"
            for c in chunks[:3]
        )
        return (
            f"*Note: AI answer generation is currently unavailable. "
            f"Here are the most relevant excerpts from your documents:*\n\n"
            f"{context_text}\n\n"
            f"**Sources:** {', '.join(sources)}"
        )
