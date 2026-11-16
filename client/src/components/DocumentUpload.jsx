import React from 'react';
import { Upload } from 'lucide-react';

export default function DocumentUpload({ onFileUpload, disabled, fileName }) {
  return (
    <div className="mb-4">
      <input
        type="file"
        id="pdf-input"
        accept=".pdf"
        onChange={onFileUpload}
        disabled={disabled}
        className="hidden"
      />
      <label
        htmlFor="pdf-input"
        className={`flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-lg cursor-pointer transition-colors bg-white hover:bg-slate-50 ${
          disabled ? 'opacity-50 cursor-not-allowed' : 'border-slate-300 hover:border-slate-400'
        }`}
      >
        <Upload className="w-6 h-6 text-slate-500 mb-2" />
        <span className="text-sm font-medium text-slate-700 text-center">
          {fileName || 'Select PDF Document'}
        </span>
      </label>
    </div>
  );
}