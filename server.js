const http = require('http');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, 'public');
const port = Number(process.env.PORT || 3000);
const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon'
};

function safeFile(urlPath) {
  const decoded = decodeURIComponent((urlPath || '/').split('?')[0]);
  const relative = decoded === '/' ? 'index.html' : decoded.replace(/^\/+/, '');
  const target = path.resolve(root, relative);
  return target.startsWith(root) ? target : null;
}

const server = http.createServer((req, res) => {
  if (req.url === '/healthz') {
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-cache' });
    return res.end('ok');
  }
  const target = safeFile(req.url);
  if (!target) return res.writeHead(400).end('Bad request');
  fs.readFile(target, (err, data) => {
    if (err) {
      if (err.code === 'ENOENT') return res.writeHead(404).end('Not found');
      return res.writeHead(500).end('Server error');
    }
    res.writeHead(200, { 'Content-Type': types[path.extname(target)] || 'application/octet-stream', 'Cache-Control': path.basename(target) === 'index.html' ? 'no-cache' : 'public, max-age=3600' });
    res.end(data);
  });
});

server.listen(port, '0.0.0.0', () => console.log(`AI Research Assistant listening on ${port}`));
