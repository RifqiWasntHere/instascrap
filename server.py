#!/usr/bin/env python3
"""
Instagram scraper server — authenticates once, serves scrape requests.

Starts an HTTP server. Authenticates on boot using cookies from .env,
then keeps the instaloader session alive for all subsequent requests.

Usage:
    python server.py                  # starts on port 8000
    python server.py --port 9000      # custom port

Endpoints:
    GET  /scrape?url=<instagram_url>  # scrape a post
    GET  /health                      # check server + session status

Stop with Ctrl+C.
"""

import argparse
import json
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import core


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_PORT = 8008


# ── .env loader ────────────────────────────────────────────────────────────

def load_env(path: Path) -> dict[str, str]:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


# ── Session manager ───────────────────────────────────────────────────────

class ScraperSession:
    """Holds the authenticated instaloader instance — created once, reused forever."""

    def __init__(self):
        self.loader: core.instaloader.Instaloader | None = None
        self.username: str | None = None
        self.is_authenticated = False
        self.auth_error: str | None = None
        self._lock = threading.Lock()

    def authenticate(self, sessionid: str, ds_user_id: str, csrftoken: str) -> None:
        """Set up and verify the instaloader session. Call once on startup."""
        loader = core.make_loader()
        core.set_session(loader, sessionid, ds_user_id, csrftoken)

        print("Verifying session…")
        try:
            username = core.verify_session(loader, ds_user_id)
            self.loader = loader
            self.username = username
            self.is_authenticated = True
            print(f"✓ Authenticated as @{username}")
        except core.AuthError as e:
            self.auth_error = str(e)
            print(f"✗ Authentication failed: {e}")

    def scrape(self, url: str, download_dir: str = "downloads") -> dict:
        """Scrape a post using the persistent session. Thread-safe."""
        with self._lock:
            return core.scrape_post(url, self.loader, download_dir=download_dir)


# Global session — lives for the entire server lifetime
session = ScraperSession()


# ── HTTP handler ──────────────────────────────────────────────────────────

class ScraperHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for /scrape and /health."""

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/health":
            self._handle_health()
        elif parsed.path == "/scrape":
            self._handle_scrape(params)
        else:
            self._respond(404, {"error": "Not found. Use /scrape?url=... or /health"})

    def _handle_health(self):
        if session.is_authenticated:
            self._respond(200, {
                "status": "ok",
                "authenticated": True,
                "username": session.username,
            })
        else:
            self._respond(503, {
                "status": "unhealthy",
                "authenticated": False,
                "error": session.auth_error or "Not authenticated",
            })

    def _handle_scrape(self, params: dict):
        if not session.is_authenticated:
            self._respond(503, {
                "error": "Not authenticated",
                "detail": session.auth_error or "Session not established",
            })
            return

        url = params.get("url", [None])[0]
        if not url:
            self._respond(400, {"error": "Missing 'url' query parameter. Usage: /scrape?url=<instagram_url>"})
            return

        download_dir = params.get("download_dir", ["downloads"])[0]

        try:
            result = session.scrape(url, download_dir=download_dir)
            # Strip full paths from image_files — make them relative to download_dir
            download_root = Path(download_dir).resolve()
            result["image_files"] = [
                str(Path(f).relative_to(download_root)) if Path(f).is_relative_to(download_root) else f
                for f in result["image_files"]
            ]
            self._respond(200, result)
            
        except core.AuthError as e:
            session.is_authenticated = False
            session.auth_error = str(e)
            self._respond(401, {"error": "Authentication failed", "detail": str(e)})
        except core.ReelVideoError as e:
            self._respond(422, {"error": "Reel/video not supported", "detail": str(e)})
        except ValueError as e:
            self._respond(400, {"error": "Invalid URL", "detail": str(e)})
        except Exception as e:
            self._respond(500, {"error": "Scrape failed", "detail": str(e)})

    def _respond(self, status: int, body: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body, indent=2, default=str).encode())

    # Suppress noisy default logging
    def log_message(self, format, *args):
        pass


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Instagram scraper server — authenticates once, serves scrape requests."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--download-dir", default="downloads", help="Directory to save output (default: ./downloads)")
    args = parser.parse_args()

    # ── Load .env ─────────────────────────────────────────────────────
    env = load_env(ENV_FILE)
    sessionid = env.get("INSTA_SESSIONID")
    ds_user_id = env.get("INSTA_DS_USER_ID")
    csrftoken = env.get("INSTA_CSRFTOKEN")

    if not sessionid or not ds_user_id or not csrftoken:
        print("✗ Missing INSTA_SESSIONID, INSTA_DS_USER_ID, or INSTA_CSRFTOKEN in .env")
        print(f"  Copy .env.example → .env and fill in the values from your browser cookies.")
        sys.exit(1)

    # ── Authenticate ──────────────────────────────────────────────────
    print("═" * 52)
    print("  instascrap server")
    print("═" * 52)
    print()
    print("Authenticating with Instagram…")

    session.authenticate(sessionid, ds_user_id, csrftoken)

    if not session.is_authenticated:
        print()
        print("✗ Could not authenticate. Fix your .env and try again.")
        sys.exit(1)

    # ── Start server ──────────────────────────────────────────────────
    server = HTTPServer(("0.0.0.0", args.port), ScraperHandler)
    print()
    print(f"✓ Server running on http://localhost:{args.port}")
    print(f"  GET /scrape?url=<instagram_url>  — scrape a post")
    print(f"  GET /health                      — check status")
    print()
    print(f"  Download dir: {Path(args.download_dir).resolve()}")
    print(f"  Ctrl+C to stop")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Server stopped.")


if __name__ == "__main__":
    main()