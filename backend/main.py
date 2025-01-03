from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import os
import uuid
import shutil
from datetime import datetime
from langchain.embeddings import OpenAIEmbeddings, CacheBackedEmbeddings
from langchain.storage import LocalFileStore
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
import fitz

# Configure logging to print to console with timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Print to console
        logging.FileHandler('app.log')  # Also save to file
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary directories
UPLOAD_DIR = "uploads"
CACHE_DIR = "embeddings_cache"
FAISS_DIR = "faiss_indexes"

for dir_path in [UPLOAD_DIR, CACHE_DIR, FAISS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# Initialize embeddings with caching
try:
    underlying_embeddings = OpenAIEmbeddings()
    fs = LocalFileStore(CACHE_DIR)
    cached_embeddings = CacheBackedEmbeddings.from_bytes_store(
        underlying_embeddings,
        fs,
        namespace=underlying_embeddings.model
    )
except Exception as e:
    logger.error(f"Failed to initialize embeddings: {str(e)}")
    raise

# Store document references
document_stores = {}

class QuestionRequest(BaseModel):
    document_id: str
    question: str

def handle_error(error: Exception) -> dict:
    """Centralized error handling function"""
    if isinstance(error, HTTPException):
        return {"status_code": error.status_code, "detail": error.detail}
    
    error_msg = str(error)
    logger.error(f"Error occurred: {error_msg}", exc_info=True)
    
    if isinstance(error, (IOError, OSError)):
        return {"status_code": 500, "detail": f"File operation failed: {error_msg}"}
    
    if "PDF" in error_msg:
        return {"status_code": 400, "detail": f"PDF processing error: {error_msg}"}
    
    if "openai" in error_msg.lower():
        return {"status_code": 503, "detail": f"AI service error: {error_msg}"}
    
    return {"status_code": 500, "detail": f"Unexpected error: {error_msg}"}

@app.post("/upload")
async def upload_pdf(file: UploadFile):
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Generate unique ID and save file
        doc_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")
        
        logger.info(f"Processing upload: {file.filename}")
        
        # Save PDF file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract text from PDF
        try:
            doc = fitz.open(file_path)
            text = " ".join(page.get_text() for page in doc)
            print(text)
            doc.close()
        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}")
            raise Exception(f"Failed to extract text from PDF: {str(e)}")
        
        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        texts = text_splitter.split_text(text)
        
        # Create vector store
        try:
            vector_store = FAISS.from_texts(texts, cached_embeddings)
            document_stores[doc_id] = vector_store
        except Exception as e:
            logger.error(f"Vector store creation failed: {str(e)}")
            raise Exception(f"Failed to process document: {str(e)}")
        
        logger.info(f"Successfully processed file: {file.filename}")
        return {
            "id": doc_id,
            "name": file.filename,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        error_details = handle_error(e)
        raise HTTPException(
            status_code=error_details["status_code"],
            detail=error_details["detail"]
        )

@app.post("/ask")
async def ask_question(request: QuestionRequest):
    try:
        logger.info(f"Processing question for document: {request.document_id}")
        
        if request.document_id not in document_stores:
            raise HTTPException(status_code=404, detail="Document not found")
        
        vector_store = document_stores[request.document_id]
        
        # Get relevant documents and generate answer
        try:
            docs = vector_store.similarity_search(request.question, k=4)
            context = "\n".join(doc.page_content for doc in docs)
            
            # Generate response using context
            response = f"Based on the context, here is the answer: {context[:500]}..."
            
            logger.info("Successfully generated answer")
            return {
                "id": str(uuid.uuid4()),
                "question": request.question,
                "answer": response,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Answer generation failed: {str(e)}")
            raise Exception(f"Failed to generate answer: {str(e)}")
            
    except Exception as e:
        error_details = handle_error(e)
        raise HTTPException(
            status_code=error_details["status_code"],
            detail=error_details["detail"]
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)