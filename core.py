"""
Core scraping logic — shared by scrap_post.py (CLI) and server.py (HTTP server).

Authenticates via session cookies, fetches image(s) + caption from an Instagram post.
"""

import re
import shutil
import sys
from pathlib import Path

import instaloader


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


def make_loader() -> instaloader.Instaloader:
    """Create a pre-configured Instaloader instance (images only, no clutter)."""
    return instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        post_metadata_txt_pattern="",
        storyitem_metadata_txt_pattern="",
    )


# ── Exceptions ────────────────────────────────────────────────────────────

class AuthError(Exception):
    """Raised when session cookies are invalid or expired."""
    pass


class ReelVideoError(Exception):
    """Raised when the post is a reel/video (not supported)."""
    pass


# ── Core scraper ──────────────────────────────────────────────────────────

def scrape_post(
    url: str,
    loader: instaloader.Instaloader,
    download_dir: str = "downloads",
) -> dict:
    """Download image(s) + caption for a single Instagram post.

    Output layout:
        downloads/<shortcode>/caption.txt
        downloads/<shortcode>/img/<image files>

    Returns dict with shortcode, caption, image_files, author, date, likes, comments, etc.

    Raises:
        AuthError: if the session is expired/invalid
        ReelVideoError: if the post is a reel/video
        ValueError: if the URL can't be parsed
        Exception: for other unexpected errors
    """
    shortcode = extract_shortcode(url)
    out_dir = Path(download_dir) / shortcode
    img_dir = out_dir / "img"
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    # Point instaloader at our img/ dir
    loader.dirname_pattern = str(img_dir)

    # ── Fetch post ────────────────────────────────────────────────────
    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
    except instaloader.exceptions.LoginRequiredException:
        raise AuthError("Instagram requires login — sessionid is expired or invalid.")
    except instaloader.exceptions.BadResponseException as e:
        err = str(e)
        if "403" in err or "login" in err.lower() or "checkpoint" in err.lower():
            raise AuthError(f"Authentication failed (server rejected the session): {e}")
        raise
    except instaloader.exceptions.ConnectionException as e:
        err = str(e)
        if "403" in err or "401" in err:
            raise AuthError(f"Authentication failed: {e}")
        raise

    # ── Caption ───────────────────────────────────────────────────────
    caption = post.caption or ""
    caption_file = out_dir / "caption.txt"
    caption_file.write_text(caption, encoding="utf-8")

    # ── Reject non-image posts ────────────────────────────────────────
    if post.typename == "GraphVideo":
        raise ReelVideoError(f"Post {shortcode} is a reel/video — only image and carousel posts are supported.")

    # ── Image(s) ─────────────────────────────────────────────────────
    loader.download_post(post, target=shortcode)

    # Flatten nested dir if instaloader created one
    nested = img_dir / shortcode
    if nested.is_dir():
        for f in nested.iterdir():
            dest = img_dir / f.name
            if not dest.exists():
                if f.is_dir():
                    shutil.move(str(f), str(dest))
                else:
                    f.rename(dest)
        if not any(nested.iterdir()):
            nested.rmdir()

    # Find image files
    image_files = sorted(
        f for f in img_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    )

    # ── Build result ──────────────────────────────────────────────────
    result = {
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

    if post.typename == "GraphSidecar":
        result["carousel_count"] = post.mediacount

    return result


def verify_session(loader: instaloader.Instaloader, ds_user_id: str) -> str:
    """Verify the instaloader session is valid by loading the user's profile.

    Returns the username if valid.

    Raises AuthError if the session is invalid.
    """
    try:
        own_profile = instaloader.Profile.from_id(loader.context, int(ds_user_id))
        return own_profile.username
    except instaloader.exceptions.LoginRequiredException:
        raise AuthError("Session rejected — your INSTA_SESSIONID has expired or is invalid.")
    except ValueError:
        raise AuthError("INSTA_DS_USER_ID is not a valid number — check .env.")
