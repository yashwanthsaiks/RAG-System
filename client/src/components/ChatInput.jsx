import React from 'react';
import { Send } from 'lucide-react';

export default function ChatInput({ question, setQuestion, onSubmit, isReady, querying }) {
  return (
    <form onSubmit={onSubmit} className="p-4 border-t border-slate-200 flex gap-2 bg-white">
      <input
        type="text"
        placeholder={isReady ? 'Ask a question about this document...' : 'Upload a document first...'}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        disabled={!isReady || querying}
        className="flex-1 px-4 py-2 border border-slate-300 rounded-md outline-none text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:bg-slate-100 disabled:cursor-not-allowed"
      />
      <button
        type="submit"
        disabled={!isReady || querying || !question.trim()}
        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
      >
        <Send className="w-4 h-4" />
      </button>
    </form>
  );
}