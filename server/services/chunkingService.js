const { RecursiveCharacterTextSplitter } = require('@langchain/textsplitters');

/**
 * Splits extracted document text into smaller context chunks.
 */
const createTextChunks = async (text, chunkSize = 1000, chunkOverlap = 200) => {
  const splitter = new RecursiveCharacterTextSplitter({
    chunkSize,
    chunkOverlap,
    separators: ['\n\n', '\n', ' ', '']
  });

  const docs = await splitter.createDocuments([text]);
  return docs;
};

module.exports = { createTextChunks };