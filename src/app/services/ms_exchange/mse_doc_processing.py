import os
import re
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
import html2text
from langchain_core.documents import Document


class EmailDocumentLoader:
    """Document loader for Microsoft Graph API emails that follows the same pattern as other loaders."""
    
    def __init__(self):
        self.chunk_size = 400  # Target tokens
        self.chunk_overlap = 100
        self.min_chunk_size = 4
        self.max_chars_per_chunk = self.chunk_size * 5  # Avg 5 chars/token

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

    def parse_api_datetime(self, dt_str):
        """Parse datetime fields from API format."""
        if not dt_str:
            return None
        try:
            if dt_str.endswith('Z'):
                return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            else:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing datetime {dt_str}: {e}")
            return None

    def extract_email_metadata(self, message: Dict) -> Dict:
        """Extract metadata from Microsoft Graph API message."""
        # Parse sender information
        sender_data = message.get("sender", {})
        sender_email_data = sender_data.get("emailAddress", {}) if sender_data else {}
        sender_name = sender_email_data.get("name", "") if sender_email_data else ""
        sender_address = sender_email_data.get("address", "") if sender_email_data else ""
        
        # Parse flag status
        flag_status = 'notFlagged'
        flag_data = message.get("flag", {})
        if flag_data and flag_data.get("flagStatus") == "flagged":
            flag_status = 'flagged'
        
        # Parse categories
        categories = message.get("categories", [])
        
        # Parse content
        content = ""
        body_data = message.get("body", {})
        if body_data and body_data.get("content"):
            content = html2text.html2text(body_data.get("content", "")).replace("\n", "    ")
        
        return {
            "email_id": message.get("id", ""),
            "subject": message.get("subject", ""),
            "sender_name": sender_name,
            "sender_address": sender_address,
            "content": content,
            "created_datetime": self.parse_api_datetime(message.get("createdDateTime")),
            "sent_datetime": self.parse_api_datetime(message.get("sentDateTime")),
            "received_datetime": self.parse_api_datetime(message.get("receivedDateTime")),
            "last_modified_datetime": self.parse_api_datetime(message.get("lastModifiedDateTime")),
            "flag_status": flag_status,
            "categories": categories,
            "has_attachments": message.get("hasAttachments", False),
            "inference_classification": message.get("inferenceClassification", ""),
            "is_read": message.get("isRead", False),
            "message_id": message.get("internetMessageId", ""),
            "conversation_id": message.get("conversationId", ""),
            "sync_timestamp": datetime.now(timezone.utc)
        }

    def create_enhanced_chunk_text(self, email_metadata: Dict, chunk_content: str) -> str:
        """Create enhanced chunk text with comprehensive contextual information."""
        # Format datetime for better readability
        received_dt = email_metadata.get("received_datetime", "Unknown")
        if isinstance(received_dt, datetime):
            received_dt = received_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Create comprehensive context
        enhanced_text = f"""Sender Name: {email_metadata.get('sender_name', 'Unknown')}
Sender Email: {email_metadata.get('sender_address', 'Unknown')}
DateTime: {received_dt}
Subject: {email_metadata.get('subject', 'No Subject')}

Email Content:
{chunk_content}"""
        
        return enhanced_text

    def create_langchain_documents(self, email_metadata: Dict, ait_id: str, document_collection: str) -> List[Document]:
        """Create LangChain documents from email metadata with proper source_id following your pattern."""
        content = email_metadata.get("content", "")
        if not content or len(content.strip()) < self.min_chunk_size:
            return []
        
        # Smart chunking
        chunks = self.smart_chunk_email(content)
        if not chunks:
            return []
        
        documents = []
        email_id = email_metadata.get("email_id", "")
        
        for chunk_index, chunk_content in enumerate(chunks):
            # Create enhanced chunk text
            enhanced_text = self.create_enhanced_chunk_text(email_metadata, chunk_content)
            sent_datetime = email_metadata.get("sent_datetime", "").isoformat() if isinstance(email_metadata.get("sent_datetime"), datetime) else str(email_metadata.get("sent_datetime", ""))
            sender_address = email_metadata.get("sender_address", "")
            # Create comprehensive metadata following your pattern
            metadata = {
                "ait_id": ait_id,
                "type": document_collection,
                "email_id": email_id,
                "file_name": f"{email_metadata.get('subject', 'No Subject')[:50]}...",  # Truncated subject as file name
                "chunk_index": chunk_index,
                "subject": email_metadata.get("subject", ""),
                "sender_name": email_metadata.get("sender_name", ""),
                "sender_address": sender_address,
                "sent_datetime": sent_datetime,
                "received_datetime": email_metadata.get("received_datetime", "").isoformat() if isinstance(email_metadata.get("received_datetime"), datetime) else str(email_metadata.get("received_datetime", "")),
                "created_datetime": email_metadata.get("created_datetime", "").isoformat() if isinstance(email_metadata.get("created_datetime"), datetime) else str(email_metadata.get("created_datetime", "")),
                "last_modified_datetime": email_metadata.get("last_modified_datetime", "").isoformat() if isinstance(email_metadata.get("last_modified_datetime"), datetime) else str(email_metadata.get("last_modified_datetime", "")),
                "flag_status": email_metadata.get("flag_status", ""),
                "categories": json.dumps(email_metadata.get("categories", [])),
                "has_attachments": email_metadata.get("has_attachments", False),
                "inference_classification": email_metadata.get("inference_classification", ""),
                "is_read": email_metadata.get("is_read", False),
                "message_id": email_metadata.get("message_id", ""),
                "conversation_id": email_metadata.get("conversation_id", ""),
                "source_id": f"email_{sender_address}_{sent_datetime}_{chunk_index}"
            }
            
            documents.append(Document(
                page_content=enhanced_text,
                metadata=metadata
            ))
        
        return documents

# Email document loader function following your pattern
async def load_email_documents(
    messages: List[Dict],
    ait_id: str,
    document_collection: str,
    logger: logging.Logger
) -> List[Document]:
    """
    Load and process email documents from Microsoft Graph API messages.
    
    Args:
        messages: List of email messages from Microsoft Graph API
        ait_id: Unique identifier for the AIT
        document_collection: Collection name (e.g., "emails", "mse_emails")
        logger: Logger instance
        
    Returns:
        List[Document]: List of processed LangChain documents
    """
    loader = EmailDocumentLoader()
    all_documents = []
    
    logger.info(f"Processing {len(messages)} emails for document creation")
    
    for message in messages:
        try:
            # Extract email metadata
            email_metadata = loader.extract_email_metadata(message)
            
            # Create LangChain documents
            documents = loader.create_langchain_documents(
                email_metadata, 
                ait_id, 
                document_collection
            )
            
            if documents:
                all_documents.extend(documents)
                logger.info(f"Created {len(documents)} document chunks for email: {email_metadata.get('subject', 'No Subject')[:50]}...")
            else:
                logger.warning(f"No chunks created for email: {email_metadata.get('subject', 'No Subject')[:50]}...")
                
        except Exception as e:
            logger.error(f"Error processing email: {e}")
            continue
    
    logger.info(f"Total documents created: {len(all_documents)}")
    return all_documents
