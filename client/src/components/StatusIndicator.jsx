import React from 'react';
import { Loader2, CheckCircle } from 'lucide-react';

export default function StatusIndicator({ uploading, indexing, isReady }) {
  return (
    <div className="space-y-2 mb-4">
      {uploading && (
        <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
          <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
          <span>Uploading & extracting text...</span>
        </div>
      )}
      {indexing && (
        <div className="flex items-center gap-2 text-xs font-medium text-slate-600">
          <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
          <span>Generating local vectors...</span>
        </div>
      )}
      {isReady && (
        <div className="flex items-center gap-2 text-xs font-medium text-emerald-600">
          <CheckCircle className="w-4 h-4" />
          <span>Document Ready for Q&A!</span>
        </div>
      )}
    </div>
  );
}