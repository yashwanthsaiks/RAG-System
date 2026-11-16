import React from 'react';

export default function MessageBubble({ message }) {
  const isUser = message.sender === 'user';

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} my-1`}>
      <div
        className={`max-w-[80%] p-3.5 rounded-lg text-sm leading-relaxed ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-none'
            : 'bg-slate-100 text-slate-800 border border-slate-200 rounded-bl-none'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.text}</p>

        {/* Source context dropdown */}
        {message.sources && message.sources.length > 0 && (
          <details className="mt-3 text-xs text-slate-500 border-t border-slate-200 pt-2">
            <summary className="cursor-pointer font-medium hover:text-slate-700">
              Retrieved Sources ({message.sources.length})
            </summary>
            <div className="mt-2 space-y-1.5">
              {message.sources.map((src, idx) => (
                <pre
                  key={idx}
                  className="p-2 bg-white rounded border border-slate-200 text-[11px] whitespace-pre-wrap font-mono text-slate-600 overflow-x-auto"
                >
                  {src}
                </pre>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}