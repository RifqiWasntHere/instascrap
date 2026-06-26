# instascrap 🍄

A tiny Instagram post scraper that yanks the image and caption out of a post link. That's it. No feed crawling, no stories, no analytics dashboards. Just give it a link and get your stuff.

Built on [Instaloader](https://instaloader.github.io/) because life's too short to wrangle Instagram's GraphQL API by hand.

## What it does

Give it an Instagram post URL → it fetches the image(s) and caption, drops them in a folder. Done.

- **Single image posts** → one image
- **Carousel posts** → all images in the set
- **Reels / videos** → nah. It'll tell you no and save the caption anyway.

You can use it as a **one-off CLI** or as a **persistent server** that authenticates once and serves requests without re-authenticating every time.

## Setup

You need session cookies from your browser. Not a login, not an API key — just three cookies. Instagram's API won't talk to you otherwise.

```bash
pip install -r requirements.txt
cp .env.example .env
```

### Getting your cookies

1. Open [instagram.com](https://www.instagram.com) in your browser and log in
2. Open **DevTools** → **Application** → **Cookies** → `https://www.instagram.com`
3. Grab these three:

| Cookie | .env key |
|---|---|
| `sessionid` | `INSTA_SESSIONID` |
| `ds_user_id` | `INSTA_DS_USER_ID` |
| `csrftoken` | `INSTA_CSRFTOKEN` |

> **Heads up:** Session cookies expire eventually. If the scraper starts failing with auth errors, just grab fresh cookies and update `.env`.

## Usage — CLI (one-off)

```bash
python scrap_post.py "https://www.instagram.com/p/ABC123/"
```

Don't forget the quotes — your shell will choke on the `?` and `&` in the URL otherwise.

## Usage — Server (persistent)

Authenticates once on startup, then keeps the session alive. Way faster for scraping multiple posts since you skip the auth overhead every time.

```bash
python server.py                  # starts on port 8000
python server.py --port 9000      # custom port
```

### Endpoints

**Scrape a post:**
```
GET /scrape?url=https://www.instagram.com/p/ABC123/
```

Returns JSON:
```json
{
  "shortcode": "ABC123",
  "caption": "the post caption...",
  "image_files": ["ABC123/img/1.jpg"],
  "author": "username",
  "likes": 1234,
  "comments": 56,
  "typename": "GraphImage",
  "download_dir": "/path/to/downloads/ABC123"
}
```

**Health check:**
```
GET /health
```

Returns:
```json
{
  "status": "ok",
  "authenticated": true,
  "username": "your_username"
}
```

### Example with curl

```bash
# Start the server
python server.py

# In another terminal — scrape a post
curl "http://localhost:8000/scrape?url=https://www.instagram.com/p/ABC123/"

# Check if the server's alive
curl http://localhost:8000/health
```

Stop the server with `Ctrl+C`.

## Output structure

```
downloads/
  └── <shortcode>/
        ├── caption.txt
        └── img/
              └── 1.jpg        (single image)
              └── 1.jpg, 2.jpg … (carousel)
```

## Why not just log in through the script?

Instagram flags programmatic logins with a security checkpoint (the "was this you?" email). Bypassing that is a whole thing. Grabbing cookies from a browser you're already logged into? Takes 30 seconds and just works.

## Why the server mode?

Every CLI call re-authenticates from scratch — read `.env`, set cookies, verify session, *then* fetch the post. That's fine for one-off use, but if you're scraping multiple posts the auth overhead repeats for every single call.

The server authenticates **once** on startup. After that, every request skips straight to fetching. The instaloader session stays warm in memory with connection pooling, so back-to-back requests are noticeably snappier.

## Have fun 🎉
