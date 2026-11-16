import React from 'react';
import { FileText } from 'lucide-react';

export default function ActiveDocCard({ docName }) {
  if (!docName) return null;

  return (
    <div className="flex items-center gap-2 p-3 bg-slate-200/60 rounded-md text-xs font-medium text-slate-800 border border-slate-300">
      <FileText className="w-4 h-4 text-slate-600 shrink-0" />
      <span className="truncate">Active: {docName}</span>
    </div>
  );
}