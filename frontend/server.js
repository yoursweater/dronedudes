const express = require('express');
const path = require('path');

const app = express();
const PORT = 3000;

// Serve static files (like index.html, script.js) from the current directory
app.use(express.static(path.join(__dirname)));

// Default route — serve index.html
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
