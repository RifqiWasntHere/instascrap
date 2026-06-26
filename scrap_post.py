#!/usr/bin/env python3
"""
Scrape an Instagram post — fetch the image and caption using Instaloader.

Authenticates via session cookies (no login/password needed).
Set INSTA_SESSIONID, INSTA_DS_USER_ID, INSTA_CSRFTOKEN in .env — see .env.example.

Usage:
    python scrap_post.py "https://www.instagram.com/p/ABC123/"

Output:
    ./downloads/<shortcode>/caption.txt  — the caption text
    ./downloads/<shortcode>/img/         — the post image(s)
"""

import argparse
import sys
from pathlib import Path

import core

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"

def load_env(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file."""
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


def _auth_error(reason: str) -> None:
    """Print a clear authentication error with instructions, then exit."""
    print()
    print("═" * 56)
    print("  ✗  AUTHENTICATION FAILED")
    print("═" * 56)
    print(f"  {reason}")
    print()
    print("  How to fix:")
    print("  1. Open instagram.com in your browser and log in")
    print("  2. Open DevTools → Application → Cookies → instagram.com")
    print("  3. Copy 'sessionid'  → INSTA_SESSIONID in .env")
    print("  4. Copy 'ds_user_id' → INSTA_DS_USER_ID in .env")
    print("  5. Copy 'csrftoken'  → INSTA_CSRFTOKEN in .env")
    print("  6. Re-run this script")
    print()
    print("  Note: Session cookies expire. If this keeps happening,")
    print("  grab fresh cookies from your browser and update .env.")
    print("═" * 56)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Scrape an Instagram post — fetch image + caption via Instaloader."
    )
    parser.add_argument(
        "url",
        help="Instagram post URL  (e.g. https://www.instagram.com/p/ABC123/)",
    )
    parser.add_argument(
        "--download-dir",
        default="downloads",
        help="Directory to save output  (default: ./downloads)",
    )
    args = parser.parse_args()

    # ── Load session from .env ────────────────────────────────────────
    env = load_env(ENV_FILE)
    sessionid = env.get("INSTA_SESSIONID")
    ds_user_id = env.get("INSTA_DS_USER_ID")
    csrftoken = env.get("INSTA_CSRFTOKEN")

    if not sessionid or not ds_user_id or not csrftoken:
        print("⚠ Missing INSTA_SESSIONID, INSTA_DS_USER_ID, or INSTA_CSRFTOKEN in .env")
        print(f"  Copy .env.example → .env and fill in the values from your browser cookies:")
        print(f"    DevTools → Application → Cookies → instagram.com → sessionid, ds_user_id, csrftoken")
        sys.exit(1)

    # ── Set up instaloader + auth ─────────────────────────────────────
    loader = core.make_loader()
    core.set_session(loader, sessionid, ds_user_id, csrftoken)
    print("✓ Session set from .env")

    # Verify
    print("Verifying session…")
    try:
        username = core.verify_session(loader, ds_user_id)
        print(f"✓ Session valid — logged in as @{username}")
    except core.AuthError as e:
        _auth_error(str(e))
    except Exception as e:
        print(f"⚠ Could not verify session ({type(e).__name__}) — proceeding anyway…")

    # ── Scrape ────────────────────────────────────────────────────────
    print(f"Fetching post…")
    try:
        result = core.scrape_post(args.url, loader, download_dir=args.download_dir)
    except core.AuthError as e:
        _auth_error(str(e))
    except core.ReelVideoError as e:
        print()
        print("═" * 56)
        print("  ✗  REEL/VIDEO — NOT SUPPORTED")
        print("═" * 56)
        print(f"  {e}")
        print("═" * 56)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)

    # ── Print result ──────────────────────────────────────────────────
    image_files = result["image_files"]
    if not image_files:
        print("⚠ No image files found — the download may have been blocked by Instagram.")
    elif len(image_files) == 1:
        print(f"✓ Caption saved ({len(result['caption'])} chars)")
        print(f"✓ Image saved")
    else:
        print(f"✓ Caption saved ({len(result['caption'])} chars)")
        print(f"✓ {len(image_files)} images saved (carousel post)")

    print()
    print("─" * 52)
    print(f"  Post      {args.url}")
    print(f"  Author    @{result['author']}")
    print(f"  Date      {result['date'][:16]}")
    print(f"  Likes     {result['likes']:,}")
    print(f"  Comments  {result['comments']:,}")
    if result["typename"] == "GraphSidecar":
        print(f"  Type      Carousel ({result['carousel_count']} items)")
    else:
        print(f"  Type      Image")
    caption = result["caption"]
    print(f"  Caption   {caption[:100]}{'…' if len(caption) > 100 else ''}")
    print(f"  Saved to  {result['download_dir']}")
    print("─" * 52)

if __name__ == "__main__":
    main()
