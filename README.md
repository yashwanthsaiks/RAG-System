# 📚 Document Assistant – RAG-Based Question Answering System

An AI-powered document assistant that allows users to upload documents and ask questions based on their content. The system uses **Retrieval-Augmented Generation (RAG)** to retrieve relevant information from uploaded documents and generate context-aware responses using a Large Language Model (LLM).

## 🚀 Project Overview

Traditional LLMs generate responses based on their training knowledge and may produce inaccurate information when answering questions about private or domain-specific documents.

This project addresses that problem by implementing a RAG pipeline that retrieves relevant document chunks and provides them as context to an LLM before generating an answer.

Users can upload documents, ask questions, and receive responses grounded in the uploaded content.

## ✨ Features

- **Document Upload:** Upload PDF, DOCX, and TXT documents.
- **Document Processing:** Extract text and split documents into manageable chunks.
- **Text Embeddings:** Convert document chunks into vector representations.
- **Vector Search:** Retrieve semantically relevant document chunks using ChromaDB.
- **LLM Integration:** Generate context-aware answers using a locally hosted LLM through Ollama.
- **Context-Aware Q&A:** Answer questions using information retrieved from uploaded documents.
- **RAG Evaluation:** Evaluate retrieval and generation performance using a Python evaluation script.

## 🏗️ Architecture

```text
                 User
                  |
                  v
           React Frontend
                  |
                  v
          Node.js Backend
                  |
                  v
          Document Upload
                  |
                  v
          Text Extraction
                  |
                  v
          Text Chunking
                  |
                  v
          Embedding Model
                  |
                  v
             ChromaDB
                  |
                  |
User Question ----+
                  |
                  v
          Query Embedding
                  |
                  v
       Semantic Similarity Search
                  |
                  v
        Relevant Document Chunks
                  |
                  v
           Prompt Generation
                  |
                  v
             Ollama LLM
                  |
                  v
          Generated Answer
                  |
                  v
             User Interface
```

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Frontend | React.js |
| Backend | Node.js |
| Database | MongoDB |
| Vector Database | ChromaDB |
| LLM Runtime | Ollama |
| AI Architecture | Retrieval-Augmented Generation (RAG) |
| Evaluation | Python |

## 🔄 RAG Workflow

### 1. Document Ingestion
- Users upload documents through the frontend.
- The backend processes the uploaded files.
- Text is extracted from supported document formats.

### 2. Text Chunking
- Extracted text is divided into smaller chunks.
- Chunking helps improve retrieval relevance and provides manageable context to the LLM.

### 3. Embedding Generation
- Each chunk is converted into a numerical vector using an embedding model.
- These vectors capture the semantic meaning of the text.

### 4. Vector Storage
- Generated embeddings and their associated document chunks are stored in ChromaDB.

### 5. Query Processing
- The user's question is converted into an embedding.
- Semantic similarity search retrieves the most relevant document chunks.

### 6. Answer Generation
- Retrieved chunks are passed to the LLM as context.
- Ollama generates a response based on the retrieved information.
- The response is returned to the frontend.

## 💻 Getting Started

### Prerequisites

Make sure you have installed:

- Node.js and npm
- Python 3.x
- Ollama
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/yashwanthsaiks/RAG-System.git
```

```bash
cd RAG-System
```

### 2. Install Frontend Dependencies

```bash
cd client
npm install
```

### 3. Install Backend Dependencies

```bash
cd ../server
npm install
```

### 4. Configure Ollama

Install Ollama and download the LLM and embedding models used by your application.

Example:

```bash
ollama pull llama3
```

Start the Ollama service:

```bash
ollama serve
```

The default local Ollama endpoint is:

```text
http://localhost:11434
```

Use the model names configured in your application.

### 5. Configure Environment Variables

Create `.env` files in the appropriate directories based on your application configuration.

Example:

```env
MONGODB_URI=your_mongodb_connection_string
OLLAMA_BASE_URL=http://localhost:11434
```

Add any other environment variables required by your implementation.

**Important:** Never commit API keys, database credentials, or `.env` files to GitHub.

### 6. Run the Application

Start the backend and frontend using the development scripts configured in their respective `package.json` files.

For example:

```bash
npm run dev
```

Run this from the relevant application directory if that script is available.

## 📊 RAG Evaluation

The project includes a Python evaluation script:

```bash
python rag_eval.py
```

The evaluation workflow can be used to assess the quality of the RAG pipeline.

Evaluation dimensions to consider:

- **Faithfulness:** Whether generated answers are supported by retrieved context.
- **Answer Relevancy:** Whether the generated answer addresses the user's question.
- **Context Precision:** Whether retrieved chunks are relevant.
- **Context Recall:** Whether the retrieval process captures the information needed to answer the question.

Evaluation results are available in:

```text
rag_eval_report.json
```

## 🔮 Future Improvements

- Implement conversation history and contextual follow-up questions.
- Improve retrieval using hybrid search.
- Add reranking for better document retrieval.
- Support additional document formats.
- Add source citations to generated answers.
- Implement comprehensive RAG evaluation and monitoring.
- Optimize chunk size and retrieval parameters.

## 👨‍💻 Author

**Yashwanth Sai K S**

GitHub: [@yashwanthsaiks](https://github.com/yashwanthsaiks)

---

⭐ If you find this project useful, consider giving the repository a star!
