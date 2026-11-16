const mongoose = require('mongoose');

const DocumentSchema = new mongoose.Schema({
  filename: { type: String, required: true },
  originalName: { type: String, required: true },
  mimeType: { type: String, required: true },
  size: { type: Number, required: true },
  extractedText: { type: String, default: '' },
  status: { 
    type: String, 
    enum: ['uploaded', 'processing', 'indexed', 'failed'], 
    default: 'uploaded' 
  },
  createdAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model('Document', DocumentSchema);