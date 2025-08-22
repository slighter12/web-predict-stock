const path = require('path');
const express = require('express');
const compression = require('compression');

const app = express();
const DIST_DIR = path.join(__dirname, 'dist');
const HTML_FILE = path.join(DIST_DIR, 'index.html');
const PORT = process.env.PORT || 8080;

app.use(compression());
app.use(express.static(DIST_DIR));

app.get('/', (req, res) => {
    res.sendFile(HTML_FILE);
});

app.listen(PORT, () => {
    console.log(`App listening on port ${PORT} ...`);
});
