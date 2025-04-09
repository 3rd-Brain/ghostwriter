
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
        
    async def store_file(self, file: BinaryIO, filename: str, user_id: str) -> str:
        """Store file in Object Storage and return file ID"""
        try:
            print("\n=== Starting file storage ===")
            print(f"Storing file: {filename}")
            print(f"User ID: {user_id}")
            
            # Generate a unique file ID
            file_id = str(uuid.uuid4())
            object_path = f"documents/{user_id}/{file_id}/{filename}"
            print(f"Generated object path: {object_path}")
            
            print("Attempting to upload to Object Storage...")
            file_content = file.read()
            
            # Handle binary files (like PDFs) and text files differently
            if filename.lower().endswith('.pdf'):
                print("Detected PDF file, storing as binary data...")
                self.storage_client.upload_from_bytes(object_path, file_content)
            else:
                # For text-based files like Markdown
                if isinstance(file_content, bytes):
                    try:
                        print("Converting bytes to text using UTF-8 decoding...")
                        file_content = file_content.decode('utf-8')
                    except UnicodeDecodeError as e:
                        print(f"UTF-8 decoding failed: {str(e)}")
                        print("Falling back to binary storage...")
                        self.storage_client.upload_from_bytes(object_path, file_content)
                        file.seek(0)
                        return file_id
                self.storage_client.upload_from_text(object_path, file_content)
            
            print("Successfully uploaded to Object Storage")
            file.seek(0)  # Reset file pointer
            return file_id
            
        except Exception as e:
            print("\n=== Error in file storage ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Error occurred at: {e.__traceback__.tb_lineno}")
            raise
    
    async def process_file_background(self, filename: str, file_id: str, user_id: str) -> Dict:
        """Process file in background after it has been stored"""
        try:
            print(f"\n=== Starting background processing for file: {filename} ===")
            print(f"File ID: {file_id}")
            print(f"User ID: {user_id}")
            
            # Retrieve file from Object Storage
            object_path = f"documents/{user_id}/{file_id}/{filename}"
            print(f"Retrieving file from path: {object_path}")
            
            # Extract text based on file type
            if filename.lower().endswith('.pdf'):
                # For PDFs, we need to read the file from storage and process it
                try:
                    print("Reading PDF from storage...")
                    file_bytes = self.storage_client.download_as_bytes(object_path)
                    print(f"Retrieved {len(file_bytes)} bytes")
                    
                    # Create a BytesIO object to simulate a file
                    import io
                    file_io = io.BytesIO(file_bytes)
                    
                    text_content = self._extract_pdf_text(file_io)
                    channel_source = "PDF"
                except Exception as e:
                    print(f"Error reading PDF from storage: {str(e)}")
                    raise
            elif filename.lower().endswith('.md'):
                try:
                    print("Reading Markdown from storage...")
                    file_content = self.storage_client.download_as_text(object_path)
                    text_content = markdown.markdown(file_content)
                    # Simple HTML to text conversion
                    text_content = text_content.replace('<p>', '').replace('</p>', '\n')
                    channel_source = "Markdown"
                except Exception as e:
                    print(f"Error reading Markdown from storage: {str(e)}")
                    raise
            else:
                raise ValueError("Unsupported file type")
                
            print(f"Successfully extracted text, length: {len(text_content)} characters")
            
            # Chunk the content
            print("Chunking content...")
            chunks = self._chunk_content(text_content)
            print(f"Created {len(chunks)} chunks")
            
            # Process each chunk
            processed_chunks = []
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1}/{len(chunks)}...")
                chunk_id = str(uuid.uuid4())
                
                print(f"Generating embedding for chunk {i+1}...")
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
                
                print(f"Uploading chunk {i+1} to AstraDB...")
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()
                print(f"Successfully uploaded chunk {i+1} to AstraDB. Response: {response.status_code}")
                
                processed_chunks.append(document)
            
            print(f"\n=== Background processing complete! ===")
            print(f"File: {filename}")
            print(f"Total chunks: {len(processed_chunks)}")
            return {"file_id": file_id, "chunks": processed_chunks}
            
        except Exception as e:
            print("\n=== Error in background processing ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Error occurred at: {e.__traceback__.tb_lineno}")
            print(f"This error occurred in the background and was not sent to the user")
    
    # For backward compatibility
    async def process_file(self, file: BinaryIO, filename: str, user_id: str) -> Dict:
        """Legacy method for direct processing (not using background tasks)"""
        file_id = await self.store_file(file, filename, user_id)
        return await self.process_file_background(filename, file_id, user_id)
        
    def _extract_pdf_text(self, file: BinaryIO) -> str:
        """Extract text from PDF file"""
        try:
            print("=== PDF Extraction Debug ===")
            print("Reading PDF file content as bytes...")
            file_bytes = file.read()
            print(f"Read {len(file_bytes)} bytes from PDF file")
            
            print("Creating PyMuPDF document...")
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            print(f"Successfully opened PDF with {len(doc)} pages")
            
            text = ""
            for i, page in enumerate(doc):
                print(f"Extracting text from page {i+1}/{len(doc)}...")
                page_text = page.get_text()
                print(f"Page {i+1}: extracted {len(page_text)} characters")
                text += page_text
            
            print(f"Total extracted text: {len(text)} characters")
            print("=== PDF Extraction Complete ===")
            return text
        except Exception as e:
            print(f"=== PDF Extraction Error ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print(f"Error occurred at line: {e.__traceback__.tb_lineno}")
            print("=== PDF Extraction Error End ===")
            raise
        
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

    
