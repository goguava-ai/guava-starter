"""
Dynamic Wikipedia RAG: searches Wikipedia on-the-fly with caching.

Uses a cache-first retrieval strategy: follow-up questions are first
checked against articles already fetched during the conversation. A new
Wikipedia search only happens when the cached context is insufficient.
This avoids redundant lookups and supports natural follow-up chains like
"What is earthquake insurance?" -> "What about in Japan?" -> "And Canada?"

Uses Vertex AI for both embedding (LanceDBStore) and answer generation
(Gemini). Query rewriting is done with Gemini to resolve pronouns across
multi-turn conversations.
"""

import guava
import os
import logging
import tempfile

import httpx
from google import genai
from guava.helpers.rag import LanceDBStore, VertexAIEmbedding
from guava.helpers.rag.chunking import chunk_document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai_client = genai.Client(vertexai=True, location="us-central1")

# Custom instructions that ask the LLM to say NEED_MORE_INFO when the
# cached context is insufficient, so we know to fetch more articles.
_TRY_INSTRUCTIONS = (
    "You are a helpful assistant. Answer the question using ONLY the provided "
    "document excerpts. If the excerpts do not contain enough information to "
    "answer the question well, respond with exactly NEED_MORE_INFO and nothing "
    "else. Otherwise, answer concisely."
)

_DEFAULT_INSTRUCTIONS = (
    "You are a virtual contact center agent. Your task is to answer questions "
    "using ONLY the provided supporting document excerpts. If the answer is not "
    "in the provided context, say so. Just answer the question — do not offer "
    "any follow-ups."
)

_REWRITE_INSTRUCTIONS = (
    "You are a query rewriter. Given a conversation history and a follow-up "
    "question, rewrite the follow-up into a standalone question. Resolve all "
    "pronouns and references. Return ONLY the rewritten question."
)

_WIKI_REWRITE_INSTRUCTIONS = (
    "You are a query rewriter. Given a conversation history and a follow-up "
    "question, rewrite the follow-up into a standalone Wikipedia article title "
    "that is most likely to answer the question. Return ONLY the article title."
)


def _rewrite_query(question: str, history: list[tuple[str, str]], instructions: str) -> str:
    if not history:
        return question
    history_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in history[-3:])
    response = genai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Conversation history:\n{history_text}\n\nFollow-up question: {question}",
        config={"system_instruction": instructions},
    )
    return response.text.strip()


def _generate_answer(chunks: list[str], question: str, instructions: str = _DEFAULT_INSTRUCTIONS) -> str:
    context = "\n\n---\n\n".join(chunks)
    response = genai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Context:\n{context}\n\nQuestion: {question}",
        config={"system_instruction": instructions},
    )
    return response.text.strip()


class DynamicWikipediaRetriever:
    """Searches Wikipedia's API and caches fetched articles for reuse."""

    def __init__(self, max_articles: int = 3, cache_size: int = 32):
        self._http = httpx.Client(
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; python-httpx/0.27)"},
        )
        self._max_articles = max_articles
        self._cache_size = cache_size
        self._article_cache: dict[str, str] = {}

    def search(self, query: str) -> list[str]:
        """Search Wikipedia and return matching article titles."""
        resp = self._http.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query,
                    "srlimit": str(self._max_articles), "format": "json"},
        )
        resp.raise_for_status()
        return [r["title"] for r in resp.json().get("query", {}).get("search", [])]

    def fetch_article(self, title: str) -> str:
        """Fetch a Wikipedia article's plain text, returning from cache if available."""
        if title in self._article_cache:
            return self._article_cache[title]
        resp = self._http.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "titles": title, "prop": "extracts",
                    "explaintext": "1", "format": "json"},
        )
        resp.raise_for_status()
        text = ""
        for page in resp.json().get("query", {}).get("pages", {}).values():
            if page.get("extract"):
                text = page["extract"]
                break
        if text:
            while len(self._article_cache) >= self._cache_size:
                del self._article_cache[next(iter(self._article_cache))]
            self._article_cache[title] = text
        return text


WIKI = DynamicWikipediaRetriever()


class WikipediaOpenQAController(guava.CallController):
    """Answers open-domain questions by dynamically fetching and caching Wikipedia articles."""

    def __init__(self):
        super().__init__()
        # Per-call state: conversation history, accumulated chunks, and a per-call LanceDB store
        self.history: list[tuple[str, str]] = []
        self._processed_titles: set[str] = set()
        # Each call gets an isolated in-memory LanceDB store (temp dir, cleared on exit)
        self._tmpdir = tempfile.mkdtemp(prefix="guava_wiki_")
        self._store = LanceDBStore(
            path=self._tmpdir,
            embedding_model=VertexAIEmbedding(client=genai_client),
        )
        self.read_script("Hello, how can I help you today?")
        self.accept_call()

    def _fetch_new_articles(self, query: str) -> bool:
        """Search Wikipedia and add any new articles to the per-call store."""
        search_query = _rewrite_query(query, self.history, _WIKI_REWRITE_INSTRUCTIONS)
        added = False
        for title in WIKI.search(search_query):
            if title not in self._processed_titles:
                text = WIKI.fetch_article(title)
                if text:
                    chunks = chunk_document(text)
                    self._store.add_texts(chunks)
                    self._processed_titles.add(title)
                    added = True
        return added

    def on_question(self, question: str) -> str:
        # Rewrite follow-ups into standalone queries
        rewritten = _rewrite_query(question, self.history, _REWRITE_INSTRUCTIONS)

        # Step 1: Try answering from articles already fetched in this call.
        if self._store.count() > 0:
            chunks = self._store.search(rewritten, k=20)
            answer = _generate_answer(chunks, rewritten, _TRY_INSTRUCTIONS)
            if "NEED_MORE_INFO" not in answer:
                self.history.append((question, answer))
                return answer

        # Step 2: Cached context was insufficient — fetch new Wikipedia articles
        if not self._fetch_new_articles(rewritten) and self._store.count() == 0:
            answer = "I'm sorry, I couldn't find any information on that topic."
            self.history.append((question, answer))
            return answer

        # Step 3: Answer from the expanded store (old + newly fetched articles)
        chunks = self._store.search(rewritten, k=20)
        answer = _generate_answer(chunks, rewritten)
        self.history.append((question, answer))
        return answer


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=WikipediaOpenQAController,
    )
