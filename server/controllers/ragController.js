const Document = require('../models/Document');
const { createTextChunks } = require('../services/chunkingService');
const { indexDocumentChunks, queryDocumentRAG } = require('../services/vectorDbService');

exports.processAndIndexDocument = async (req, res) => {
  const { documentId } = req.body;

  try {
    const document = await Document.findById(documentId);
    if (!document) {
      return res.status(404).json({ error: 'Document not found.' });
    }

    document.status = 'processing';
    await document.save();

    // Chunking
    const chunks = await createTextChunks(document.extractedText);

    // Embed & Index to ChromaDB
    const result = await indexDocumentChunks(document._id, chunks);

    document.status = 'indexed';
    await document.save();

    return res.status(200).json({
      message: 'Document indexed into ChromaDB successfully.',
      documentId: document._id,
      chunksIndexed: result.count,
      status: document.status
    });
  } catch (error) {
    await Document.findByIdAndUpdate(documentId, { status: 'failed' });
    return res.status(500).json({ error: error.message });
  }
};

exports.askQuestion = async (req, res) => {
  const { documentId, question } = req.body;

  if (!documentId || !question) {
    return res.status(400).json({ error: 'Both documentId and question are required.' });
  }

  try {
    const ragResult = await queryDocumentRAG(question, documentId);
    return res.status(200).json({
      question,
      answer: ragResult.answer,
      sources: ragResult.sourceContext
    });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
};