from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import subprocess

FLAG_PATH = Path("/flag")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self.reply(200, "ok")
        if parsed.path == "/api/run":
            command = parse_qs(parsed.query).get("cmd", [""])[0]
            if not command:
                return self.reply(400, "missing cmd")
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
                output = (result.stdout or "") + (result.stderr or "")
                return self.reply(200, output or f"exit={result.returncode}")
            except Exception as exc:
                return self.reply(500, str(exc))
        if parsed.path == "/api/status":
            return self.reply(200, "running")
        return self.reply(404, "not found")

    def reply(self, status, body):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    if not FLAG_PATH.exists():
        FLAG_PATH.write_text("FLAG{local-demo}")
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
