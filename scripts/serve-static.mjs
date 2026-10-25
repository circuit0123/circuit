// Static file server with brotli and cache headers, like a real host (python http.server sends everything uncompressed, which skews Lighthouse).
// Usage: node scripts/serve-static.mjs <folder> <port>
import http from "node:http"; import { readFileSync, existsSync, statSync } from "node:fs"; import { brotliCompressSync } from "node:zlib"; import { join, extname } from "node:path";
const root = process.argv[2], port = +process.argv[3];
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2", ".webp": "image/webp", ".avif": "image/avif", ".png": "image/png", ".mp4": "video/mp4", ".ico": "image/x-icon", ".txt": "text/plain", ".xml": "application/xml" };
const cache = new Map();
http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname); if (p.endsWith("/")) p += "index.html";
  let f = join(root, p); if (!existsSync(f) || statSync(f).isDirectory()) { res.writeHead(404); return res.end("nf"); }
  const ext = extname(f); const raw = readFileSync(f);
  const compress = [".html", ".js", ".css", ".txt", ".xml", ".ico"].includes(ext) && /br/.test(req.headers["accept-encoding"] ?? "");
  if (compress && !cache.has(f)) cache.set(f, brotliCompressSync(raw));
  res.writeHead(200, { "content-type": types[ext] ?? "application/octet-stream", "cache-control": p.startsWith("/_next/static") || p.startsWith("/brand") || p.startsWith("/shots") ? "public, max-age=31536000, immutable" : "public, max-age=0", ...(compress ? { "content-encoding": "br" } : {}) });
  res.end(compress ? cache.get(f) : raw);
}).listen(port);
