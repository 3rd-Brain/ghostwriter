
import os
from typing import BinaryIO, Dict, Optional
from replit.object_storage import Client
import fitz  # PyMuPDF for PDF processing
import markdown
from datetime import datetime
import requests
from openai import OpenAI
import uuid

class DocumentProcessor:
    def __init__(self):
        self.storage_client = Client()
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
    def process_file(self, file: BinaryIO, filename: str, user_id: str) -> Dict:
        """Process uploaded file and store in Object Storage with chunked vector storage"""
        print(f"\n=== Processing file: {filename} for user: {user_id} ===")
        
        # Store file in Object Storage
        file_id = str(uuid.uuid4())
        object_path = f"documents/{user_id}/{file_id}/{filename}"
        print(f"Storing file at: {object_path}")
        self.storage_client.upload_from_file(object_path, file)
        
        # Extract text based on file type
        if filename.lower().endswith('.pdf'):
            text_content = self._extract_pdf_text(file)
            channel_source = "PDF"
        elif filename.lower().endswith('.md'):
            text_content = self._extract_markdown_text(file)
            channel_source = "Markdown"
        else:
            raise ValueError("Unsupported file type")
            
        # Chunk the content
        chunks = self._chunk_content(text_content)
        
        # Process each chunk
        processed_chunks = []
        for chunk in chunks:
            chunk_id = str(uuid.uuid4())
            embedding = self._generate_embedding(chunk)
            
            print(f"Processing chunk {len(processed_chunks) + 1}, length: {len(chunk)} characters")
            print("Generating embedding...")
            
            # Store in AstraDB with the specified structure
            url = f"{os.environ.get('ASTRA_DB_API_ENDPOINT')}/api/json/v1/user_content_keyspace/user_source_content"
            
            document = {
                "content_id": chunk_id,
                "user_id": user_id,
                "content": chunk,
                "source": filename,
                "channel_source": channel_source,
                "$vector": embedding,
                "context": "NA"
            }
            
            payload = {
                "insertOne": {
                    "document": document
                }
            }
            
            headers = {
                "Token": os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER"),
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            processed_chunks.append(document)
            
        return {"file_id": file_id, "chunks": processed_chunks}
        
    def _extract_pdf_text(self, file: BinaryIO) -> str:
        """Extract text from PDF file"""
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
        
    def _extract_markdown_text(self, file: BinaryIO) -> str:
        """Extract text from Markdown file"""
        print("Extracting text from Markdown file...")
        content = file.read().decode('utf-8')
        print(f"Raw content length: {len(content)} characters")
        html = markdown.markdown(content)
        text = html.replace('<p>', '').replace('</p>', '\n')
        print(f"Processed text length: {len(text)} characters")
        return text
        
    def _generate_embedding(self, text: str) -> list:
        """Generate embedding using OpenAI API"""
        response = self.openai_client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
        
    def _chunk_content(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list:
        """Chunk content with overlap"""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            
            # Adjust end to not split words
            if end < text_length:
                # Find the next space after the chunk_size
                while end < text_length and text[end] != ' ':
                    end += 1
            
            # Add chunk
            chunks.append(text[start:end])
            
            # Move start position for next chunk, accounting for overlap
            start = end - overlap
            
            # Adjust start to not split words
            if start > 0:
                # Find the next space
                while start < text_length and text[start] != ' ':
                    start += 1
                
        return chunks

    
