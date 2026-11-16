require('dotenv').config();
const express = require('express');
const cors = require('cors');
const connectDB = require('./config/db');

const documentRoutes = require('./routes/documentRoutes');
const ragRoutes = require('./routes/ragRoutes');

const app = express();

// Connect MongoDB Atlas
connectDB();

// Middleware
app.use(cors());
app.use(express.json());

// API Endpoints
app.use('/api/documents', documentRoutes);
app.use('/api/rag', ragRoutes);

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`RAG Portal backend running on port ${PORT}`);
});