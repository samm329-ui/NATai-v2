import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import config

class VectorStoreService:
    def __init__(self):
        self._embeddings = None
        self.vector_store = None
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        os.makedirs(getattr(config, 'VECTOR_STORE_PATH', 'database/vector_store'), exist_ok=True)
        os.makedirs(getattr(config, 'LEARNING_DATA_PATH', 'database/learning_data'), exist_ok=True)
        os.makedirs(getattr(config, 'CHATS_PATH', 'database/chats_data'), exist_ok=True)

    @property
    def embeddings(self):
        if self._embeddings is None:
            print("[VectorStore] Loading embeddings model...")
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        return self._embeddings

    def load_or_create_vectorstore(self):
        """Loads the FAISS index from disk, or creates a new one if it doesn't exist."""
        index_path = os.path.join(config.VECTOR_STORE_PATH, "index.faiss")
        if os.path.exists(index_path):
            try:
                # allow_dangerous_deserialization is required in newer LangChain versions to load local FAISS files safely
                self.vector_store = FAISS.load_local(
                    folder_path=str(config.VECTOR_STORE_PATH), 
                    embeddings=self.embeddings,
                    allow_dangerous_deserialization=True 
                )
                print("[VectorStore] Loaded existing FAISS index from disk.")
            except Exception as e:
                print(f"[VectorStore] Error loading FAISS index: {e}. Rebuilding a fresh one.")
                self._create_empty_store()
        else:
            self._create_empty_store()

    def _create_empty_store(self):
        """Initializes an empty FAISS index."""
        empty_doc = Document(page_content="System memory initialized.", metadata={"source": "system"})
        self.vector_store = FAISS.from_documents([empty_doc], self.embeddings)
        self.save_vectorstore()
        print("[VectorStore] Created new empty FAISS index.")

    def save_vectorstore(self):
        """Saves the current FAISS index to disk."""
        if self.vector_store:
            self.vector_store.save_local(str(config.VECTOR_STORE_PATH))

    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]] = None):
        """Adds raw text documents to the vector store on the fly."""
        if not texts:
            return
            
        docs = [Document(page_content=t, metadata=m or {}) for t, m in zip(texts, metadatas or [{}]*len(texts))]
        split_docs = self.text_splitter.split_documents(docs)
        
        if self.vector_store is None:
            self.vector_store = FAISS.from_documents(split_docs, self.embeddings)
        else:
            self.vector_store.add_documents(split_docs)
            
        self.save_vectorstore()

    def add_learning_files(self):
        """Scans the learning_data and chats_data folders and indexes everything."""
        print("[VectorStore] Indexing learning data and past chats for Natasha's memory...")
        documents = []
        
        # 1. Read static learning data (.txt files)
        for txt_file in Path(config.LEARNING_DATA_PATH).glob("*.txt"):
            try:
                with open(txt_file, "r", encoding="utf-8") as f:
                    text = f.read()
                    if text.strip():
                        documents.append(Document(page_content=text, metadata={"source": txt_file.name, "type": "learning_data"}))
            except Exception as e:
                print(f"[VectorStore] Error reading {txt_file}: {e}")

        # 2. Read past conversation history (.json files)
        for json_file in Path(config.CHATS_PATH).glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    chat_text = f"Session ID: {data.get('session_id', 'Unknown')}\n"
                    for msg in data.get("messages", []):
                        chat_text += f"{msg.get('role', '').capitalize()}: {msg.get('content', '')}\n"
                        
                    if chat_text.strip():
                        documents.append(Document(page_content=chat_text, metadata={"source": json_file.name, "type": "chat_history"}))
            except Exception as e:
                print(f"[VectorStore] Error reading {json_file}: {e}")

        if documents:
            # Process and embed the documents
            split_docs = self.text_splitter.split_documents(documents)
            self.vector_store = FAISS.from_documents(split_docs, self.embeddings)
            self.save_vectorstore()
            print(f"[VectorStore] Successfully embedded and indexed {len(split_docs)} chunks of memory.")
            return {"status": "success", "chunks_added": len(split_docs)}
        
        print("[VectorStore] No learning documents or chats found to index.")
        return {"status": "success", "chunks_added": 0}

    def get_relevant_context(self, query: str, k: int = 5) -> str:
        """Retrieves the top k most relevant memory chunks for the user's query."""
        if not self.vector_store:
            return ""
            
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Crucial: Escape curly braces so LangChain doesn't think they are formatting variables
            context = context.replace("{", "{{").replace("}", "}}")
            return context
        except Exception as e:
            print(f"[VectorStore] Memory retrieval error: {e}")
            return ""

    def get_status(self) -> Dict[str, Any]:
        """Returns the current status of the vector database."""
        if not self.vector_store:
            return {
                "loaded": False, 
                "document_count": 0, 
                "path": str(getattr(config, 'VECTOR_STORE_PATH', ''))
            }
        
        try:
            count = self.vector_store.index.ntotal
            return {
                "loaded": True, 
                "document_count": count, 
                "model": "sentence-transformers/all-MiniLM-L6-v2", 
                "path": str(getattr(config, 'VECTOR_STORE_PATH', ''))
            }
        except:
            return {
                "loaded": True, 
                "document_count": -1, 
                "path": str(getattr(config, 'VECTOR_STORE_PATH', ''))
            }

vector_store_service = VectorStoreService()