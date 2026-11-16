const fs = require('fs');
const pdfParse = require('pdf-parse-fork');
const Document = require('../models/Document');

exports.uploadDocument = async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No PDF file provided.' });
    }

    const dataBuffer = fs.readFileSync(req.file.path);
    // ChatGPT generated code to handle PDF parsing with custom options to mute warnings and errors during font parsing
    const options = {
      pagerender: function(pageData) {
        // Mute console.warn and console.error during font parsing
        const origWarn = console.warn;
        const origError = console.error;
        console.warn = () => {};
        console.error = () => {};

        return pageData.getTextContent().then(function(textContent) {
          console.warn = origWarn;
          console.error = origError;

          let lastY, text = '';
          for (let item of textContent.items) {
            if (lastY == item.transform[5] || !lastY) {
              text += item.str;
            } else {
              text += '\n' + item.str;
            }
            lastY = item.transform[5];
          }
          return text;
        });
      }
    };
    
    // Parse PDF buffer directly
    const pdfData = await pdfParse(dataBuffer, options);

    const newDoc = new Document({
      filename: req.file.filename,
      originalName: req.file.originalname,
      mimeType: req.file.mimetype,
      size: req.file.size,
      extractedText: pdfData.text,
      status: 'uploaded'
    });

    await newDoc.save();

    return res.status(201).json({
      message: 'File uploaded and parsed successfully.',
      document: {
        id: newDoc._id,
        originalName: newDoc.originalName,
        characterCount: pdfData.text.length,
        status: newDoc.status
      }
    });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
};