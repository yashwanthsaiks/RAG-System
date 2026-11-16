import React from 'react';

export default function Header() {
  return (
    <header className="bg-slate-900 text-white p-6 text-center shadow-md">
      <h1 className="text-2xl font-bold tracking-tight">Document Assistant (Local RAG)</h1>
      <p className="text-sm text-slate-400 mt-1">
        Upload a PDF document and ask questions locally via Ollama
      </p>
    </header>
  );
}