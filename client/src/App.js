import React, { useState } from 'react';
import axios from 'axios';
import Header from './components/Header';
import DocumentUpload from './components/DocumentUpload';
import StatusIndicator from './components/StatusIndicator';
import ActiveDocCard from './components/ActiveDocCard';
import ChatHistory from './components/ChatHistory';
import ChatInput from './components/ChatInput';

const API_BASE = 'http://127.0.0.1:5000/api';

export default function App() {
  const [file, setFile] = useState(null);
  const [documentId, setDocumentId] = useState(null);
  const [docName, setDocName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [isReady, setIsReady] = useState(false);

  const [question, setQuestion] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [querying, setQuerying] = useState(false);

  const handleFileUpload = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setUploading(true);
    setIsReady(false);

    try {
      const formData = new FormData();
      formData.append('document', selectedFile);

      const uploadRes = await axios.post(`${API_BASE}/documents/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const uploadedDocId = uploadRes.data.document.id;
      setDocumentId(uploadedDocId);
      setDocName(uploadRes.data.document.originalName);
      setUploading(false);

      setIndexing(true);
      await axios.post(`${API_BASE}/rag/index`, { documentId: uploadedDocId });

      setIndexing(false);
      setIsReady(true);
    } catch (err) {
      console.error('Error during document processing:', err);
      alert(err.response?.data?.error || 'Document processing failed.');
      setUploading(false);
      setIndexing(false);
    }
  };

  const handleSendQuestion = async (e) => {
    e.preventDefault();
    if (!question.trim() || !documentId || !isReady) return;

    const userMsg = question.trim();
    setQuestion('');
    setChatHistory((prev) => [...prev, { sender: 'user', text: userMsg }]);
    setQuerying(true);

    try {
      const res = await axios.post(`${API_BASE}/rag/query`, {
        documentId,
        question: userMsg
      });

      setChatHistory((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: res.data.answer,
          sources: res.data.sources
        }
      ]);
    } catch (err) {
      console.error('Query Error:', err);
      setChatHistory((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: 'An error occurred while generating the answer from the document.'
        }
      ]);
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto my-6 bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden flex flex-col h-[750px]">
      <Header />

      <main className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-80 border-r border-slate-200 p-5 bg-slate-50 flex flex-col">
          <h2 className="text-sm font-semibold text-slate-700 mb-4 uppercase tracking-wider">
            Document Manager
          </h2>

          <DocumentUpload
            onFileUpload={handleFileUpload}
            disabled={uploading || indexing}
            fileName={file?.name}
          />

          <StatusIndicator
            uploading={uploading}
            indexing={indexing}
            isReady={isReady}
          />

          <ActiveDocCard docName={docName} />
        </aside>

        {/* Main Chat Panel */}
        <section className="flex-1 flex flex-col bg-white">
          <ChatHistory chatHistory={chatHistory} querying={querying} />

          <ChatInput
            question={question}
            setQuestion={setQuestion}
            onSubmit={handleSendQuestion}
            isReady={isReady}
            querying={querying}
          />
        </section>
      </main>
    </div>
  );
}