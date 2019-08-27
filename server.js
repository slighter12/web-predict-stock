const path = require('path');
const express = require('express');
const compression = require('compression');

const app = express(),
            DIST_DIR = __dirname,
            HTML_FLIE = path.join(DIST_DIR, 'index.html');
const PORT = process.env.PORT || 8080;

app.use(compression());
app.use(express.static(DIST_DIR));

app.get('/', (req, res) => {
    res.sendFile(HTML_FILE);
});

app.listen(PORT, () => {
    console.log(`App listen to ${PORT} ...`)
});
