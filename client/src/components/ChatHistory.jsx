import React from 'react';
import MessageBubble from './MessageBubble';
import { Loader2 } from 'lucide-react';

export default function ChatHistory({ chatHistory, querying }) {
  return (
    <div className="flex-1 p-6 overflow-y-auto space-y-3 flex flex-col">
      {chatHistory.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
          Upload a document on the left to start asking questions.
        </div>
      ) : (
        chatHistory.map((msg, index) => (
          <MessageBubble key={index} message={msg} />
        ))
      )}

      {querying && (
        <div className="flex items-center gap-2 p-3.5 bg-slate-100 text-slate-600 text-sm rounded-lg border border-slate-200 w-fit">
          <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
          <span>Generating answer using Llama 3.2...</span>
        </div>
      )}
    </div>
  );
}