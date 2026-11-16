const express = require('express');
const router = express.Router();
const upload = require('../middlewares/uploadMiddleware');
const { uploadDocument } = require('../controllers/documentController');

router.post('/upload', upload.single('document'), uploadDocument);

module.exports = router;