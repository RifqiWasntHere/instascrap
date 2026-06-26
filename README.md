# instascrap 

A tiny Instagram post scraper that yanks the image and caption out of a post link. That's it. Made this for my DoksliPlis fun project.

Built on [Instaloader](https://instaloader.github.io/) because my patience's too short to fuh around with Instagram's GraphQL API.

## What it does

Give it an Instagram post URL → it fetches the image(s) and caption, drops them in a folder. Done.

- **Single image posts** → one image
- **Carousel posts** → all images in the set
- **Reels / videos** → nah. It'll tell you no and save the caption anyway.

## Setup

Needs session cookies from browser (three cookies, listed below).

```bash
# Install deps
pip install -r requirements.txt

# Copy the example env and fill in your cookies
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

That's it. You're in.

> **Heads up:** Session cookies expire eventually. If the scraper starts failing with auth errors, just grab fresh cookies from your browser and update `.env`.

## Usage

```bash
python scrap_post.py "https://www.instagram.com/p/ABC123/"
```

Don't be a dumbass like me, and quote the input link, or else your shell will choke on the `?` and `&` in the URL.

### Output

```
downloads/
  └── ABC123/
        ├── caption.txt
        └── img/
              └── 1.jpg
```

Carousel posts get multiple images in `img/`.


## Cheers fellers
