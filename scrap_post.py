#!/usr/bin/env python3
"""
Scrape an Instagram post — fetch the image and caption using Instaloader.

Authenticates via session cookies (no login/password needed).
Set INSTA_SESSIONID, INSTA_DS_USER_ID, INSTA_CSRFTOKEN in .env — see .env.example.

Usage:
    python scrap_post.py https://www.instagram.com/p/ABC123/

Output:
    ./downloads/<shortcode>/caption.txt  — the caption text
    ./downloads/<shortcode>/img/         — the post image(s)
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

import instaloader


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"


# ── .env loader ────────────────────────────────────────────────────────────

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


# ── Helpers ────────────────────────────────────────────────────────────────

def extract_shortcode(url: str) -> str:
    """Pull the shortcode from an Instagram post/reel/tv URL."""
    match = re.search(r"instagram\.com/(p|reel|tv)/([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError(f"Could not extract shortcode from URL: {url}")
    return match.group(2)


def set_session(
    loader: instaloader.Instaloader,
    sessionid: str,
    ds_user_id: str,
    csrftoken: str,
) -> None:
    """Set the Instagram session cookies directly (no login flow).

    Replicates what instaloader.load_session() does: sets cookies,
    X-CSRFToken header, and username so is_logged_in returns True.
    """
    s = loader.context._session
    s.cookies.set("sessionid", sessionid, domain=".instagram.com", path="/")
    s.cookies.set("ds_user_id", ds_user_id, domain=".instagram.com", path="/")
    s.cookies.set("csrftoken", csrftoken, domain=".instagram.com", path="/")
    s.headers.update({"X-CSRFToken": csrftoken})
    loader.context.username = f"user_{ds_user_id}"


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


# ── Core scraper ──────────────────────────────────────────────────────────

def scrape_post(
    url: str,
    sessionid: str | None = None,
    ds_user_id: str | None = None,
    csrftoken: str | None = None,
    download_dir: str = "downloads",
) -> dict:
    """Download image(s) + caption for a single Instagram post.

    Output layout:
        downloads/<shortcode>/caption.txt
        downloads/<shortcode>/img/<image files>

    Returns dict with shortcode, caption, image_files, author, date, likes, comments, etc.
    """
    shortcode = extract_shortcode(url)
    out_dir = Path(download_dir) / shortcode
    img_dir = out_dir / "img"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Configure instaloader — pics + caption only, no clutter
    # dirname_pattern controls where instaloader saves files
    loader = instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        post_metadata_txt_pattern="",
        storyitem_metadata_txt_pattern="",
    )
    # Tell instaloader to save into our img/ subdirectory
    loader.dirname_pattern = str(img_dir)

    # ── Set session ───────────────────────────────────────────────────
    if sessionid and ds_user_id and csrftoken:
        set_session(loader, sessionid, ds_user_id, csrftoken)
        print(f"✓ Session set from .env")

        # Verify the session actually works before trying to fetch the post
        print("Verifying session…")
        try:
            own_profile = instaloader.Profile.from_id(loader.context, int(ds_user_id))
            print(f"✓ Session valid — logged in as @{own_profile.username}")
        except instaloader.exceptions.LoginRequiredException:
            _auth_error("Session rejected — your INSTA_SESSIONID has expired or is invalid.")
        except ValueError:
            _auth_error("INSTA_DS_USER_ID is not a valid number — check .env.")
        except Exception as e:
            print(f"⚠ Could not verify session ({type(e).__name__}) — proceeding anyway…")
    else:
        print("⚠ Missing session credentials — scraping without login (will likely fail)")
        print("  Add INSTA_SESSIONID, INSTA_DS_USER_ID, and INSTA_CSRFTOKEN to .env (see .env.example)")

    # ── Fetch post ────────────────────────────────────────────────────
    print(f"Fetching post {shortcode}…")
    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
    except instaloader.exceptions.LoginRequiredException:
        _auth_error("Instagram requires login for this post — your sessionid is expired or invalid.")
    except instaloader.exceptions.BadResponseException as e:
        err = str(e)
        if "403" in err or "login" in err.lower() or "checkpoint" in err.lower():
            _auth_error(f"Authentication failed (server rejected the session): {e}")
        print(f"✗ Could not fetch post — the link may be wrong.\n  {e}")
        sys.exit(1)
    except instaloader.exceptions.ConnectionException as e:
        err = str(e)
        if "403" in err or "401" in err:
            _auth_error(f"Authentication failed: {e}")
        print(f"✗ Connection error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)

    # ── Caption ───────────────────────────────────────────────────────
    caption = post.caption or ""
    caption_file = out_dir / "caption.txt"
    caption_file.write_text(caption, encoding="utf-8")
    print(f"✓ Caption saved ({len(caption)} chars)")

    # ── Reject non-image posts ────────────────────────────────────────
    if post.typename == "GraphVideo":
        print()
        print("═" * 56)
        print("  ✗  REEL/VIDEO — NOT SUPPORTED")
        print("═" * 56)
        print("  This post is a reel/video, not an image or carousel.")
        print("  This script only downloads posts with images.")
        print()
        print(f"  Caption saved to: {caption_file}")
        print("═" * 56)

        # Clean up — caption is still useful, keep out_dir
        sys.exit(1)

    # ── Image(s) ─────────────────────────────────────────────────────
    # instaloader downloads into dirname_pattern (our img/ dir).
    # The target arg is used for filename generation inside that dir.
    img_dir.mkdir(parents=True, exist_ok=True)
    loader.download_post(post, target=shortcode)

    # instaloader may create an extra nesting level: img/<shortcode>/...
    # Flatten it so images are directly in img/
    nested = img_dir / shortcode
    if nested.is_dir():
        for f in nested.iterdir():
            dest = img_dir / f.name
            if not dest.exists():
                if f.is_dir():
                    shutil.move(str(f), str(dest))
                else:
                    f.rename(dest)
        # Remove empty nested dir
        if not any(nested.iterdir()):
            nested.rmdir()

    # Find image files in img_dir (including subdirs for carousel)
    image_files = sorted(
        f for f in img_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    )

    if not image_files:
        print("⚠ No image files found in img/ — the download may have been blocked by Instagram.")
    elif len(image_files) == 1:
        print(f"✓ Image saved: img/{image_files[0].relative_to(img_dir)}")
    else:
        print(f"✓ {len(image_files)} images saved in img/ (carousel post)")

    # ── Summary ───────────────────────────────────────────────────────
    print()
    print("─" * 52)
    print(f"  Post      {url}")
    print(f"  Author    @{post.owner_username}")
    print(f"  Date      {post.date_utc:%Y-%m-%d %H:%M UTC}")
    print(f"  Likes     {post.likes:,}")
    print(f"  Comments  {post.comments:,}")
    if post.typename == "GraphSidecar":
        print(f"  Type      Carousel ({post.mediacount} items)")
    else:
        print(f"  Type      Image")
    print(f"  Caption   {caption[:100]}{'…' if len(caption) > 100 else ''}")
    print(f"  Saved to  {out_dir.resolve()}")
    print("─" * 52)

    return {
        "shortcode": shortcode,
        "caption": caption,
        "image_files": [str(f) for f in image_files],
        "author": post.owner_username,
        "date": post.date_utc.isoformat(),
        "likes": post.likes,
        "comments": post.comments,
        "typename": post.typename,
        "download_dir": str(out_dir.resolve()),
    }


# ── CLI ───────────────────────────────────────────────────────────────────

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
        print()

    result = scrape_post(
        url=args.url,
        sessionid=sessionid,
        ds_user_id=ds_user_id,
        csrftoken=csrftoken,
        download_dir=args.download_dir,
    )
    return result


if __name__ == "__main__":
    main()
