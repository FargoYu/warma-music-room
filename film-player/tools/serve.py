"""Static server for the player page (range requests included, so audio can seek)."""
import http.server, os, sys, socketserver

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def guess_type(self, path):
        if path.endswith(".svg"):
            return "image/svg+xml"
        if path.endswith(".webm"):
            return "video/webm"
        if path.endswith(".m4s"):
            return "video/mp4"
        return super().guess_type(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), H) as s:
        print("serving", ROOT, "on", port, flush=True)
        s.serve_forever()
