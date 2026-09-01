// Serves dist/ on http://127.0.0.1:4173 so you can check the build locally
// before deploying. localhost counts as a secure origin, so the login screen's
// crypto.subtle password hashing behaves exactly as it will in production.
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const dist = resolve(dirname(fileURLToPath(import.meta.url)), "..", "dist");
const port = 4173;

createServer((req, res) => {
  try {
    const body = readFileSync(resolve(dist, "index.html"));
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(body);
  } catch {
    res.writeHead(404).end("build first: npm run build");
  }
}).listen(port, "127.0.0.1", () => {
  console.log(`preview: http://127.0.0.1:${port}  (ctrl+c to stop)`);
});
