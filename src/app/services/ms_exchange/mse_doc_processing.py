import html2text
import os
import re
import json
import hashlib
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams
from sentence_transformers import SentenceTransformer
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv(override=True)

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Initialize clients
qdrant_client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT,
    api_key=QDRANT_API_KEY
)

# Initialize embedding model
embedding_model = SentenceTransformer(EMBEDDING_MODEL)

class EmailVectorService:
    """Service for creating and managing email vector embeddings with LangChain integration."""

    def __init__(self):
        self.chunk_size = 500  # Target tokens
        self.chunk_overlap = 150
        self.min_chunk_size = 150
        self.max_chars_per_chunk = self.chunk_size * 5  # Avg 6 chars/token

    async def initialize_collection(self, ait_id):
        """Initialize Qdrant collection for email embeddings."""
        try:
            # Check if collection exists
            collections = qdrant_client.get_collections()
            collection_exists = any(col.name == ait_id for col in collections.collections)
            
            if not collection_exists:
                # Create collection with proper vector configuration
                qdrant_client.create_collection(
                    collection_name=ait_id,
                    vectors_config=VectorParams(
                        size=384,  # Dimension for all-MiniLM-L6-v2
                        distance=Distance.COSINE
                    )
                )
                logging.info(f"Created collection: {ait_id}")
            
            return True
        except Exception as e:
            logging.error(f"Error initializing collection: {e}")
            return False    

    def _clean_content(self, content: str) -> str:
        """Clean and normalize email content while preserving structure."""
        content = html2text.html2text(content)
        return content.strip()

    def smart_chunk_email(self, content: str) -> List[str]:
        """Character-aware chunking with sentence/paragraph preservation."""
        if not content or len(content.strip()) < self.min_chunk_size:
            return [content] if content.strip() else []

        content = self._clean_content(content)
        paragraphs = self._split_into_paragraphs(content)

        chunks, current_chunk = [], ""

        for paragraph in paragraphs:
            if len(paragraph) > self.max_chars_per_chunk:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                # Break long paragraph by sentences
                sentences = self._split_into_sentences(paragraph)
                chunks.extend(self._chunk_sentences(sentences))
            else:
                if len(current_chunk) + len(paragraph) + 2 > self.max_chars_per_chunk:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = self._get_overlap_content(current_chunk, paragraph)
                    else:
                        current_chunk = paragraph
                else:
                    current_chunk += "\n\n" + paragraph if current_chunk else paragraph

        if current_chunk and len(current_chunk.strip()) >= self.min_chunk_size:
            chunks.append(current_chunk.strip())

        return [chunk for chunk in chunks if len(chunk.strip()) >= self.min_chunk_size]

    def _split_into_paragraphs(self, content: str) -> List[str]:
        return [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]

    def _split_into_sentences(self, content: str) -> List[str]:
        raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', content)
        sentences = []
        for s in raw_sentences:
            if '\n' in s:
                sentences.extend([part.strip() for part in s.split('\n') if part.strip()])
            else:
                sentences.append(s.strip())
        return [s for s in sentences if s]

    def _chunk_sentences(self, sentences: List[str]) -> List[str]:
        chunks, current_chunk = [], ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 > self.max_chars_per_chunk:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = self._get_overlap_content(current_chunk, sentence)
                else:
                    chunks.extend(self._split_long_sentence(sentence))
            else:
                current_chunk += " " + sentence if current_chunk else sentence

        if current_chunk and len(current_chunk.strip()) >= self.min_chunk_size:
            chunks.append(current_chunk.strip())
        return chunks

    def _get_overlap_content(self, current_chunk: str, next_content: str) -> str:
        words = current_chunk.split()
        if len(words) > self.chunk_overlap:
            return " ".join(words[-self.chunk_overlap:]) + " " + next_content
        return next_content

    def _split_long_sentence(self, sentence: str) -> List[str]:
        breakpoints = [',', ';', ':', ' - ', ' and ', ' or ', ' but ', ' however ', ' therefore ']
        for bp in breakpoints:
            if bp in sentence and len(sentence) > self.max_chars_per_chunk:
                parts = sentence.split(bp)
                chunks, current = [], ""
                for i, part in enumerate(parts):
                    segment = part + (bp if i < len(parts) - 1 else "")
                    if len(current) + len(segment) > self.max_chars_per_chunk:
                        if current:
                            chunks.append(current.strip())
                            current = segment
                        else:
                            chunks.extend(self._split_by_words(segment))
                    else:
                        current += segment
                if current:
                    chunks.append(current.strip())
                return [c for c in chunks if len(c.strip()) >= self.min_chunk_size]
        return self._split_by_words(sentence)

    def _split_by_words(self, text: str) -> List[str]:
        words = text.split()
        chunks, current = [], []
        for word in words:
            current.append(word)
            if len(" ".join(current)) > self.max_chars_per_chunk:
                if len(current) > 1:
                    chunks.append(" ".join(current[:-1]))
                    current = [word]
                else:
                    chunks.append(word)
                    current = []
        if current:
            chunks.append(" ".join(current))
        return chunks
    
    def create_comprehensive_metadata(self,ait_id, email_data: Dict, chunk_index: int, chunk_content: str) -> Dict:
        """Create comprehensive metadata for each chunk with all email information."""
        return {
            "ait_id": ait_id,
            "type": "logs_mse_email",
            "chunk_index": chunk_index,
            "chunk_id": self._generate_chunk_id(email_data.get("email_id", ""), chunk_index),
            "subject": email_data.get("subject", ""),
            "sender_name": email_data.get("sender_name", ""),
            "sender_address": email_data.get("sender_address", ""),
            "received_datetime": email_data.get("received_datetime", "").isoformat() if isinstance(email_data.get("received_datetime"), datetime) else str(email_data.get("received_datetime", "")),
            "sent_datetime": email_data.get("sent_datetime", "").isoformat() if isinstance(email_data.get("sent_datetime"), datetime) else str(email_data.get("sent_datetime", "")),
            "message_id": email_data.get("message_id", ""),
            "thread_id": email_data.get("thread_id", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "page_content": chunk_content
        }
    
    def create_enhanced_chunk_text(self, email_data: Dict, chunk_content: str) -> str:
        """Create enhanced chunk text with comprehensive contextual information."""
        # Format datetime for better readability
        received_dt = email_data.get("received_datetime", "Unknown")
        if isinstance(received_dt, datetime):
            received_dt = received_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        sent_dt = email_data.get("sent_datetime", "Unknown")
        if isinstance(sent_dt, datetime):
            sent_dt = sent_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Create comprehensive context
        enhanced_text = f"""Sender Name: {email_data.get('sender_name', 'Unknown')}
Sender Email: {email_data.get('sender_address', 'Unknown')}
Received DateTime: {received_dt}
Sent DateTime: {sent_dt}
Subject: {email_data.get('subject', 'No Subject')}

Email Content:
{chunk_content}"""
        
        return enhanced_text
    
    def _generate_chunk_id(self, email_id: str, chunk_index: int) -> str:
        """Generate unique chunk ID."""
        return hashlib.md5(f"{email_id}_{chunk_index}".encode()).hexdigest()
    
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for given texts."""
        try:
            embeddings = embedding_model.encode(texts, convert_to_tensor=False)
            return embeddings.tolist()
        except Exception as e:
            logging.error(f"Error creating embeddings: {e}")
            return []
    
    async def store_email_embeddings(self, ait_id, email_data: Dict) -> Tuple[int, int]:
        """
        Process email and store embeddings in Qdrant with comprehensive metadata.
        Returns (stored_chunks, skipped_chunks)
        """
        try:
            content = email_data.get("content", "")
            if not content or len(content.strip()) < self.min_chunk_size:
                logging.warning(f"Email {email_data.get('email_id', 'unknown')} content too short or empty")
                return 0, 1
            
            # Smart chunking
            chunks = self.smart_chunk_email(content)
            if not chunks:
                logging.warning(f"No valid chunks created for email {email_data.get('email_id', 'unknown')}")
                return 0, 1
            
            stored_chunks = 0
            skipped_chunks = 0
            
            logging.info(f"Processing {len(chunks)} chunks for email {email_data.get('email_id', 'unknown')}")
            
            for chunk_index, chunk_content in enumerate(chunks):
                try:
                    # Create enhanced chunk text for embedding
                    enhanced_text = self.create_enhanced_chunk_text(email_data, chunk_content)
                    
                    # Create comprehensive metadata
                    metadata = self.create_comprehensive_metadata(ait_id ,email_data, chunk_index, chunk_content)
                    
                    # Generate chunk ID
                    chunk_id = self._generate_chunk_id(email_data.get("email_id", ""), chunk_index)
                    
                    # Check if chunk already exists
                    existing_points = qdrant_client.scroll(
                        collection_name=ait_id,
                        scroll_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="chunk_id",
                                    match=models.MatchValue(value=chunk_id)
                                )
                            ]
                        ),
                        limit=1
                    )
                    payload = {}
                    page_content = metadata.get("page_content")
                    metadata.pop("page_content", None)
                    payload["metadata"] = metadata
                    payload["page_content"] = page_content
                    
                    if existing_points[0]:  # Chunk already exists
                        logging.info(f"Chunk {chunk_index} already exists for email {email_data.get('email_id', '')}")
                        skipped_chunks += 1
                        continue
                    
                    # Create embedding
                    embedding = await self.create_embeddings([enhanced_text])
                    if not embedding:
                        logging.error(f"Failed to create embedding for chunk {chunk_index}")
                        skipped_chunks += 1
                        continue
                    
                    # Store in Qdrant
                    qdrant_client.upsert(
                        collection_name=ait_id,
                        points=[
                            models.PointStruct(
                                id=chunk_id,
                                vector=embedding[0],
                                payload=payload
                            )
                        ]
                    )
                    
                    stored_chunks += 1
                    logging.info(f"Stored embedding for chunk {chunk_index} of email {email_data.get('email_id', '')}")
                    
                except Exception as e:
                    logging.error(f"Error processing chunk {chunk_index}: {e}")
                    skipped_chunks += 1
                    continue
            
            logging.info(f"Email {email_data.get('email_id', 'unknown')}: {stored_chunks} stored, {skipped_chunks} skipped")
            return stored_chunks, skipped_chunks
            
        except Exception as e:
            logging.error(f"Error in store_email_embeddings: {e}")
            return 0, len(self.smart_chunk_email(email_data.get("content", "")))

# Search functionality for vector database with LangChain integration
vector_service = EmailVectorService()

async def search_email_embeddings(
    query: str,
    ait_id: str,
    limit: int = 10,
    score_threshold: float = 0.7,
    filters: Optional[Dict] = None
) -> List[Document]:
    """
    Search email embeddings using vector similarity with optional filters.
    Returns LangChain Document objects with correct nested metadata structure.
    """
    try:
        # Create query embedding
        query_embedding = await vector_service.create_embeddings([query])
        if not query_embedding:
            return []

        # Build filter conditions
        filter_conditions = [
            models.FieldCondition(
                key="metadata.ait_id",  # because ait_id is inside the metadata
                match=models.MatchValue(value=ait_id)
            )
        ]

        # Add any additional filters
        if filters:
            for key, value in filters.items():
                metadata_key = f"metadata.{key}"
                if isinstance(value, list):
                    filter_conditions.append(
                        models.FieldCondition(
                            key=metadata_key,
                            match=models.MatchAny(any=value)
                        )
                    )
                else:
                    filter_conditions.append(
                        models.FieldCondition(
                            key=metadata_key,
                            match=models.MatchValue(value=value)
                        )
                    )

        # Search Qdrant
        search_results = qdrant_client.search(
            collection_name=ait_id,
            query_vector=query_embedding[0],
            query_filter=models.Filter(must=filter_conditions),
            limit=limit,
            score_threshold=score_threshold
        )

        # Format results into LangChain Documents
        documents = []
        for result in search_results:
            payload = result.payload
            page_content = payload.get("page_content", "")
            metadata = payload.get("metadata", {})

            # Add score and chunk_id to metadata
            metadata.update({
                "score": result.score,
                "chunk_id": result.id,
            })

            documents.append(
                Document(
                    page_content=page_content,
                    metadata=metadata
                )
            )

        return documents

    except Exception as e:
        logging.error(f"Error searching embeddings: {e}")
        return []
        
if __name__ == "__main__":
    import asyncio
    print(asyncio.run(search_email_embeddings("lets meet my friend", "66b5dc91-e747-41a6-8ce7-5e37b87ce5e2", score_threshold=0.2)))