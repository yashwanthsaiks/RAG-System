const express = require('express');
const router = express.Router();
const { processAndIndexDocument, askQuestion } = require('../controllers/ragController');

router.post('/index', processAndIndexDocument);
router.post('/query', askQuestion);

module.exports = router;