
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
        try:
            print("\n=== Starting file processing ===")
            print(f"Processing file: {filename}")
            print(f"User ID: {user_id}")
            
            # Store file in Object Storage
            file_id = str(uuid.uuid4())
            object_path = f"documents/{user_id}/{file_id}/{filename}"
            print(f"Generated object path: {object_path}")
            
            print("Attempting to upload to Object Storage...")
            file_content = file.read()
            if isinstance(file_content, bytes):
                file_content = file_content.decode('utf-8')
            self.storage_client.upload_from_text(object_path, file_content)
            print("Successfully uploaded to Object Storage")
            file.seek(0)  # Reset file pointer for subsequent operations
        
            # Extract text based on file type
            print(f"Extracting text from file type: {filename.split('.')[-1].upper()}")
            if filename.lower().endswith('.pdf'):
                text_content = self._extract_pdf_text(file)
                channel_source = "PDF"
            elif filename.lower().endswith('.md'):
                text_content = self._extract_markdown_text(file)
                channel_source = "Markdown"
            else:
                raise ValueError("Unsupported file type")
            print(f"Successfully extracted text, length: {len(text_content)} characters")
            
            # Chunk the content
            chunks = self._chunk_content(text_content)
            
            # Process each chunk
            processed_chunks = []
            for chunk in chunks:
                chunk_id = str(uuid.uuid4())
                embedding = self._generate_embedding(chunk)
            
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
                
                print(f"Uploading chunk {len(processed_chunks) + 1} to AstraDB...")
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()
                print(f"Successfully uploaded chunk to AstraDB. Response: {response.status_code}")
                
                processed_chunks.append(document)
            
            print(f"\nProcessing complete! Total chunks: {len(processed_chunks)}")
            return {"file_id": file_id, "chunks": processed_chunks}
            
        except Exception as e:
            print("\n=== Error in file processing ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Error occurred at: {e.__traceback__.tb_lineno}")
            raise
        
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

    
