const { OllamaEmbeddings, ChatOllama } = require('@langchain/ollama');
const { CloudClient } = require('chromadb');

// Initialize Cloud ChromaDB Client
const chromaClient = new CloudClient({
  apiKey: process.env.CHROMA_API_KEY,
  tenant: process.env.CHROMA_TENANT,
  database: process.env.CHROMA_DATABASE
});

const OLLAMA_HOST = process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434';

// Local Embedding Model
const embeddingsModel = new OllamaEmbeddings({
  model: 'nomic-embed-text',
  baseUrl: OLLAMA_HOST
});

// Local LLM with extended timeout for model loading
const llmModel = new ChatOllama({
  model: 'llama3.2',
  baseUrl: OLLAMA_HOST,
  temperature: 0.2,
  clientOptions: {
    timeout: 300000 // 5-minute HTTP timeout
  }
});

/**
 * Embeds document text chunks locally and indexes them into ChromaDB.
 */
const indexDocumentChunks = async (documentId, chunks) => {
  try {
    const dummyEmbeddingFunction = {
  generate: async (texts) => []
};
    const collection = await chromaClient.getOrCreateCollection({
      name: 'document_embeddings_ollama',
      embeddingFunction: dummyEmbeddingFunction
    });

    const ids = [];
    const embeddings = [];
    const documents = [];
    const metadatas = [];

    for (let i = 0; i < chunks.length; i++) {
      const chunkText = chunks[i].pageContent;
      const vector = await embeddingsModel.embedQuery(chunkText);

      ids.push(`${documentId}-chunk-${i}`);
      embeddings.push(vector);
      documents.push(chunkText);
      metadatas.push({
        documentId: documentId.toString(),
        chunkIndex: i
      });
    }

    await collection.add({ ids, embeddings, documents, metadatas });
    return { success: true, count: chunks.length };
  } catch (error) {
    console.error('Ollama/ChromaDB Indexing Error:', error);
    throw error;
  }
};

/**
 * Performs vector similarity search and generates answer using local Ollama LLM.
 */
const queryDocumentRAG = async (queryText, documentId, topK = 4) => {
  try {
    const dummyEmbeddingFunction = {
  generate: async (texts) => []
};
    const collection = await chromaClient.getCollection({ 
      name: 'document_embeddings_ollama',
      embeddingFunction: dummyEmbeddingFunction
    });

    // Step 1: Embed input query
    const queryVector = await embeddingsModel.embedQuery(queryText);

    // Step 2: Query ChromaDB for relevant vector matches
    const queryResults = await collection.query({
      queryEmbeddings: [queryVector],
      nResults: topK,
      where: { documentId: documentId.toString() }
    });

    const matchedTexts = queryResults.documents[0] || [];
    const context = matchedTexts.join('\n\n---\n\n');

    // Step 3: Formulate prompt for local LLM
    const prompt = `You are an expert document assistant. Use the following context retrieved from the user's document to answer the question clearly and accurately. If the information is not present in the context, respond by saying "The document does not contain this information."

Context:
${context}

Question:
${queryText}

Answer:`;

    const response = await llmModel.invoke(prompt);
    return { answer: response.content, sourceContext: matchedTexts };
  } catch (error) {
    console.error('Ollama RAG Query Error:', error);
    throw error;
  }
};

module.exports = { indexDocumentChunks, queryDocumentRAG };