# 🌐 Gallery-DL Web Extractor & Telegram Bot

A high-performance media extraction suite with a **modern Web Frontend UI** and an optional **Telegram Bot**, powered by `gallery-dl`. Paste links from any supported platform (Twitter/X, Instagram, Reddit, Pinterest, Imgur, Pixiv, Danbooru, etc.), and extract all direct high-resolution image & video URLs with live previews, search/filtering, and instant export tools.

---

## ✨ Features

### 🌐 Web Frontend Interface
- 🎯 **Visual Media Grid & Compact List Views**: Instant visual preview for images, video playback, and direct audio files.
- 📋 **Batch Link Mode & Clipboard Paste**: Paste single links or bulk multiple URLs at once.
- ⚡ **Realtime Search & Media Type Filtering**: Filter results on the fly by type (`Images`, `Videos`, `Audio`) or search by filename / URL query.
- 💾 **Export Options**: 
  - One-click **Copy All** to clipboard.
  - Export as `.txt` (plain URL list), `.json` (full structured metadata), or `.m3u` (media playlist).
- 🌐 **Telegra.ph 1-Click Publishing**: Instantly generate a clean Telegra.ph web page from the extracted media links.
- 🕘 **Local Extraction History**: Access recently extracted links without re-fetching.
- 🎨 **Modern Dark & Light Mode**: Fluid, responsive design with glassmorphism touches and clean typography.

### 🤖 Telegram Bot
- Send or forward any supported link to the bot.
- Automatically extracts links and publishes them to a Telegra.ph page or direct chunked messages.
- User access control support (`ALLOWED_USERS`).

---

## 🚀 Running the Web Frontend

### Option 1: Local Python (Fastest)

1. Activate your virtual environment and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the web server:
   ```bash
   python server.py
   ```
3. Open your browser at [**http://localhost:8000**](http://localhost:8000).

---

### Option 2: Deploy to Render (1-Click)

1. Push your repository to **GitHub** / **GitLab**.
2. Log into [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Web Service** (or use **Blueprints** with [`render.yaml`](file:///home/ranit/RH/gallery-dl-bot/render.yaml)).
3. Select your repository. Render will automatically detect the [`Dockerfile`](file:///home/ranit/RH/gallery-dl-bot/Dockerfile).
4. Set **Runtime** to `Docker` and click **Create Web Service**.
5. Render will build and deploy the application with dynamic port routing and health check at `/api/health`.

---

### Option 3: Local Docker & Docker Compose

```bash
docker-compose up -d --build
```
Access the web frontend at `http://localhost:8000`.

---

## 🤖 Running the Telegram Bot

1. Set your `BOT_TOKEN` in `.env`:
   ```bash
   BOT_TOKEN=your_telegram_bot_token_here
   ```
2. Start the bot:
   ```bash
   python bot.py
   ```

---

## 📄 Project Structure

- [`server.py`](file:///home/ranit/RH/gallery-dl-bot/server.py) - FastAPI web server & REST API (`/api/extract`, `/api/telegraph`).
- [`extractor.py`](file:///home/ranit/RH/gallery-dl-bot/extractor.py) - Core `gallery-dl` extraction & Telegra.ph publishing module.
- [`frontend/`](file:///home/ranit/RH/gallery-dl-bot/frontend/)
  - [`index.html`](file:///home/ranit/RH/gallery-dl-bot/frontend/index.html) - Single-page web application UI.
  - [`style.css`](file:///home/ranit/RH/gallery-dl-bot/frontend/style.css) - Responsive styling & theme design system.
  - [`app.js`](file:///home/ranit/RH/gallery-dl-bot/frontend/app.js) - Interactive client logic, filters, and media viewer.
- [`bot.py`](file:///home/ranit/RH/gallery-dl-bot/bot.py) - Telegram bot application.
- [`requirements.txt`](file:///home/ranit/RH/gallery-dl-bot/requirements.txt) - Python dependencies (`fastapi`, `uvicorn`, `gallery-dl`, `httpx`, `python-telegram-bot`).
- [`Dockerfile`](file:///home/ranit/RH/gallery-dl-bot/Dockerfile) - Multi-service container specification.
