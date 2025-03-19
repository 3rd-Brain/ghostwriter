
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
        """Process uploaded file and store in Object Storage"""
        # Generate unique ID for the file
        file_id = str(uuid.uuid4())
        
        # Store file in Object Storage
        object_path = f"documents/{user_id}/{file_id}/{filename}"
        self.storage_client.upload_from_file(object_path, file)
        
        # Extract text based on file type
        if filename.lower().endswith('.pdf'):
            text_content = self._extract_pdf_text(file)
        elif filename.lower().endswith('.md'):
            text_content = self._extract_markdown_text(file)
        else:
            raise ValueError("Unsupported file type")
            
        # Generate embedding
        embedding = self._generate_embedding(text_content)
        
        # Store metadata in AstraDB
        metadata = self._store_metadata(
            file_id=file_id,
            user_id=user_id,
            filename=filename,
            text_content=text_content,
            embedding=embedding
        )
        
        return metadata
        
    def _extract_pdf_text(self, file: BinaryIO) -> str:
        """Extract text from PDF file"""
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
        
    def _extract_markdown_text(self, file: BinaryIO) -> str:
        """Extract text from Markdown file"""
        content = file.read().decode('utf-8')
        html = markdown.markdown(content)
        # Simple HTML to text conversion
        return html.replace('<p>', '').replace('</p>', '\n')
        
    def _generate_embedding(self, text: str) -> list:
        """Generate embedding using OpenAI API"""
        response = self.openai_client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
        
    def _store_metadata(self, file_id: str, user_id: str, filename: str,
                       text_content: str, embedding: list) -> Dict:
        """Store file metadata and embedding in AstraDB"""
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
        
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_documents"
        
        document = {
            "file_id": file_id,
            "user_id": user_id,
            "filename": filename,
            "content": text_content,
            "upload_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "$vector": embedding
        }
        
        payload = {
            "insertOne": {
                "document": document
            }
        }
        
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        return document
