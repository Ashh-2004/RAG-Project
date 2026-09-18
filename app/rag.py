import os
import glob
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.documents import Document

from app.config import settings


class TwoStageReranker:
    """
    Two-stage retrieval reranker leveraging HuggingFace CrossEncoder (or Cohere Rerank).
    Reranks top-10 vector candidates down to the top-3 most relevant document chunks.
    """
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.cross_encoder = None
        self._load_reranker()

    def _load_reranker(self):
        try:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(self.model_name)
            print(f"[RAG Reranker] Loaded CrossEncoder model: {self.model_name}")
        except Exception as e:
            print(f"[RAG Reranker Warning] Could not load CrossEncoder model '{self.model_name}': {e}. Using fallback scoring.")
            self.cross_encoder = None

    def rerank(self, query: str, documents: List[Document], top_n: int = 3) -> List[Document]:
        """
        Reranks a list of candidate Document chunks for a given query and returns top_n documents.
        """
        if not documents:
            return []

        if len(documents) <= top_n:
            return documents

        # Stage 2: CrossEncoder Scoring
        if self.cross_encoder:
            try:
                pairs = [[query, doc.page_content] for doc in documents]
                scores = self.cross_encoder.predict(pairs)
                
                # Pair documents with scores and sort in descending order
                doc_score_pairs = list(zip(documents, scores))
                doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
                
                reranked_docs = [doc for doc, score in doc_score_pairs[:top_n]]
                return reranked_docs
            except Exception as e:
                print(f"[RAG Reranker Error] Reranking failed: {e}. Returning initial top_n candidates.")

        # Fallback if CrossEncoder is unavailable
        return documents[:top_n]


class RAGPipeline:
    """
    Advanced RAG Pipeline featuring:
    1. Metadata Filtering (category & file_name tags).
    2. Two-Stage Retrieval (Top-10 Chroma similarity search -> Top-3 CrossEncoder reranking).
    3. Strict missing-context handling.
    """
    STRICT_NOT_FOUND_MSG = ""

    def __init__(self):
        self.vector_store: Chroma = None
        self.source_documents_by_category: Dict[str, List[Document]] = {}
        self.llm = None
        self.reranker = TwoStageReranker()
        self._initialize_pipeline()

    @staticmethod
    def derive_category_from_filename(filename: str) -> str:
        """
        Extracts policy category tag from document filename.
        e.g., 'wfh_policy.txt' -> 'wfh', 'leave_policy.txt' -> 'leave'.
        """
        clean_name = Path(filename).stem.lower()
        if "wfh" in clean_name or "remote" in clean_name:
            return "wfh"
        elif "leave" in clean_name or "vacation" in clean_name:
            return "leave"
        elif "travel" in clean_name or "reimbursement" in clean_name:
            return "travel"
        elif "security" in clean_name or "it" in clean_name:
            return "it_security"
        return clean_name.replace("_policy", "").replace("policy", "").strip("_") or "general"

    def _initialize_pipeline(self):
        """
        Loads document texts, enriches every document chunk with metadata tags:
        {"category": "<policy_type>", "file_name": "<filename>", "source": "<filename>"}
        and initializes Chroma vector database.
        """
        documents: List[Document] = []
        data_path = Path(settings.data_dir)

        if data_path.exists():
            for file_path in glob.glob(str(data_path / "*.txt")):
                file_name = Path(file_path).name
                category = self.derive_category_from_filename(file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if content.strip():
                            document = Document(
                                page_content=content,
                                metadata={
                                    "category": category,
                                    "file_name": file_name,
                                    "source": file_name
                                }
                            )
                            documents.append(document)
                            self.source_documents_by_category.setdefault(category, []).append(document)
                except Exception as e:
                    print(f"[RAG Ingestion] Error reading file {file_path}: {e}")

        # Text Splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap
        )
        chunks = text_splitter.split_documents(documents) if documents else []

        # Use local embeddings so retrieval stays available even when OpenAI billing/quota is unavailable.
        embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)

        if settings.openai_api_key and settings.openai_api_key != "your_openai_api_key_here":
            try:
                self.llm = ChatOpenAI(
                    model=settings.openai_model,
                    openai_api_key=settings.openai_api_key,
                    temperature=0.0,
                    max_tokens=1024
                )
            except Exception as e:
                print(f"[LLM Initialization Warning]: {e}. Using offline synthesis fallback.")

        # Initialize Vector Store with Enriched Metadata Chunks
        if chunks:
            self.vector_store = Chroma.from_documents(
                documents=chunks,
                embedding=embeddings
            )
        else:
            self.vector_store = Chroma(embedding_function=embeddings)

    def extract_topic(self, query_text: str) -> str:
        stop_words = {
            "what", "is", "are", "the", "policy", "for", "on", "about", "how", "does",
            "company", "guidelines", "rules", "can", "i", "do", "we", "have", "a", "an",
            "tell", "me", "show"
        }
        words = [w.strip("?,.!") for w in query_text.split() if w.lower().strip("?,.!") not in stop_words]
        if words:
            return " ".join(words)
        return "this topic"

    def search_company_documents(
        self,
        query: str,
        category: Optional[str] = None,
        top_k_initial: int = 10,
        top_n: int = 3
    ) -> Tuple[List[Document], List[str]]:
        """
        Two-Stage Retrieval with Metadata Filtering:
        - Stage 1: Vector similarity search fetching top-10 chunks (with optional category filter).
        - Stage 2: Cross-Encoder reranking returning top-3 highest-scoring chunks.
        """
        if not self.vector_store:
            return [], []

        # For explicit/inferred policy categories, use the complete source document so answers do not omit middle sections.
        where_filter = None
        if category:
            normalized_cat = category.lower().strip()
            category_docs = self.source_documents_by_category.get(normalized_cat)
            if category_docs:
                sources = [doc.metadata.get("file_name") or doc.metadata.get("source", "unknown") for doc in category_docs]
                return category_docs, list(dict.fromkeys(sources))
            where_filter = {"category": normalized_cat}

        try:
            # Stage 1: Vector similarity search (Top-10 candidates)
            if where_filter:
                results_with_score = self.vector_store.similarity_search_with_score(
                    query,
                    k=top_k_initial,
                    filter=where_filter
                )
            else:
                results_with_score = self.vector_store.similarity_search_with_score(
                    query,
                    k=top_k_initial
                )
        except Exception as e:
            print(f"[RAG Search Error]: {e}")
            return [], []

        if not results_with_score:
            return [], []

        # Candidate filtering threshold
        candidate_docs: List[Document] = []
        for doc, score in results_with_score:
            if score <= 1.35:
                candidate_docs.append(doc)

        if not candidate_docs:
            return [], []

        # Stage 2: CrossEncoder Reranking (Reranks 10 candidates -> Top 3)
        reranked_docs = self.reranker.rerank(query, candidate_docs, top_n=top_n)

        # Collect unique source filenames
        sources: List[str] = []
        for doc in reranked_docs:
            src = doc.metadata.get("file_name") or doc.metadata.get("source", "unknown")
            if src not in sources:
                sources.append(src)

        return reranked_docs, sources

    def query(
        self,
        query_text: str,
        category: Optional[str] = None,
        k_initial: int = 10,
        top_n: int = 3
    ) -> Tuple[str, List[str]]:
        """
        Executes two-stage retrieval and generates answer.
        Returns (answer_string, list_of_sources).
        """
        topic = self.extract_topic(query_text)
        not_found_msg = f"I couldn't find information about {topic} in the provided company documents."

        # Perform two-stage search with optional metadata filter
        matching_docs, sources = self.search_company_documents(
            query=query_text,
            category=category,
            top_k_initial=k_initial,
            top_n=top_n
        )

        if not matching_docs:
            return not_found_msg, []

        context = "\n---\n".join([doc.page_content for doc in matching_docs])

        # Generate answer using LLM if available
        if self.llm:
            system_prompt = (
                "You are an AI Knowledge Assistant for company policies.\n"
                "Answer the user's question STRICTLY based on the provided context below.\n"
                "Write complete responses and finish your final sentence fully.\n"
                "If you use a multi-point list, include every relevant point from the context and always finish the list without truncation.\n"
                "If the context does not contain the answer, reply ONLY with: "
                f"'{not_found_msg}'\n\n"
                f"Context:\n{context}"
            )
            try:
                response = self.llm.invoke([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query_text}
                ])
                answer = response.content.strip()
                if not answer or not_found_msg in answer:
                    return not_found_msg, []
                return answer, sources
            except Exception as e:
                print(f"[LLM Execution Error]: {e}")

        # Intelligent offline synthesis fallback
        answer = self._synthesize_offline_answer(query_text, matching_docs, not_found_msg)
        if answer == not_found_msg:
            return not_found_msg, []
        return answer, sources

    def _synthesize_offline_answer(self, query_text: str, docs: List[Document], not_found_msg: str) -> str:
        stop_words = {
            "what", "is", "are", "the", "company", "policy", "policies", "for", "about", "how",
            "does", "and", "or", "in", "on", "at", "to", "a", "an", "of", "with", "can", "i",
            "we", "have", "tell", "me", "show"
        }
        query_terms = [
            word.lower().strip("?,.!")
            for word in query_text.split()
            if word.lower().strip("?,.!") not in stop_words and len(word.strip("?,.!")) > 2
        ]
        combined_context = "\n".join(doc.page_content for doc in docs).lower()

        if query_terms and not any(term in combined_context for term in query_terms):
            return not_found_msg

        cleaned_lines: List[str] = []
        seen_lines = set()

        for doc in docs:
            for line in doc.page_content.split("\n"):
                line_clean = line.rstrip()
                stripped = line_clean.strip()

                if not stripped or stripped.strip("-").strip() == "":
                    continue

                if stripped not in seen_lines:
                    cleaned_lines.append(line_clean)
                    seen_lines.add(stripped)

        if not cleaned_lines:
            return not_found_msg

        return "Based on company policy:\n\n" + "\n".join(cleaned_lines)


# Global instance of RAG pipeline
rag_pipeline = RAGPipeline()
