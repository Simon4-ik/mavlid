import os
import sys
import asyncio
import logging

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import mimetypes
mimetypes.init()
mimetypes.types_map[".webp"] = "image/webp"

from aiohttp import web
from dotenv import load_dotenv

from backend.bot import TelegramMiniAppBot

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(name)s: %(message)s"
)
logger = logging.getLogger("server")

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

def _get_pdf_path():
    candidates = [os.getenv("PDF_FILE_PATH", ""), "mavlid.pdf", "Мавлид_ан-Набий_(1).pdf"]
    for c in candidates:
        if c:
            p = os.path.join(BASE_DIR, c)
            if os.path.exists(p):
                return p
    for f in os.listdir(BASE_DIR):
        if f.lower().endswith(".pdf"):
            return os.path.join(BASE_DIR, f)
    return os.path.join(BASE_DIR, "mavlid.pdf")

def _normalize_webapp_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return "http://localhost:8080"
    if not (url.startswith("http://") or url.startswith("https://")):
        url = f"https://{url}"
    if url.startswith("http://") and not ("localhost" in url or "127.0.0.1" in url):
        url = "https://" + url[len("http://"):]
    return url.rstrip("/")

PDF_PATH = _get_pdf_path()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBAPP_URL = _normalize_webapp_url(os.getenv("WEBAPP_URL", "http://localhost:8080"))
PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")

TOTAL_PAGES = 24  # Known from PDF inspection

async def handle_index(request: web.Request) -> web.Response:
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_file):
        return web.Response(text="Frontend index.html not found", status=404)
    with open(index_file, "r", encoding="utf-8") as f:
        content = f.read()
    return web.Response(
        text=content,
        content_type="text/html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Access-Control-Allow-Origin": "*"
        }
    )

async def handle_book_info(request: web.Request) -> web.Response:
    file_size = os.path.getsize(PDF_PATH) if os.path.exists(PDF_PATH) else 0
    return web.json_response({
        "title": "Мавлид ан-Набий",
        "description": "Пайғамбаримиз соллаллоҳу алайҳи васалламнинг муборак мавлидлари",
        "totalPages": TOTAL_PAGES,
        "fileSizeBytes": file_size,
        "author": "Mawlid an-Nabiy"
    }, headers={"Access-Control-Allow-Origin": "*"})

async def handle_pdf(request: web.Request) -> web.StreamResponse:
    if not os.path.exists(PDF_PATH):
        return web.Response(text="PDF file not found", status=404)

    file_size = os.path.getsize(PDF_PATH)
    range_header = request.headers.get("Range")

    headers = {
        "Content-Type": "application/pdf",
        "Accept-Ranges": "bytes",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Range, Content-Type, Accept",
        "Access-Control-Expose-Headers": "Content-Range, Content-Length, Accept-Ranges",
        "Cache-Control": "public, max-age=86400"
    }

    if not range_header:
        # Full content response
        headers["Content-Length"] = str(file_size)
        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)
        with open(PDF_PATH, "rb") as f:
            while chunk := f.read(64 * 1024):
                await response.write(chunk)
        await response.write_eof()
        return response

    # Parse Range: bytes=start-end
    try:
        range_str = range_header.replace("bytes=", "").strip()
        parts = range_str.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            headers["Content-Range"] = f"bytes */{file_size}"
            return web.Response(status=416, headers=headers)

        length = end - start + 1
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(length)

        response = web.StreamResponse(status=206, headers=headers)
        await response.prepare(request)

        with open(PDF_PATH, "rb") as f:
            f.seek(start)
            bytes_left = length
            while bytes_left > 0:
                chunk_size = min(64 * 1024, bytes_left)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                await response.write(chunk)
                bytes_left -= len(chunk)

        await response.write_eof()
        return response
    except Exception as e:
        logger.error(f"Error serving PDF range request: {e}")
        return web.Response(status=500, text=str(e))

async def handle_cors_preflight(request: web.Request) -> web.Response:
    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type, Accept",
            "Access-Control-Max-Age": "86400"
        }
    )

async def start_background_bot(app: web.Application):
    if BOT_TOKEN and BOT_TOKEN.strip() and not BOT_TOKEN.startswith("YOUR_"):
        bot = TelegramMiniAppBot(token=BOT_TOKEN, webapp_url=WEBAPP_URL, pdf_path=PDF_PATH)
        app["tg_bot"] = bot
        app["bot_task"] = asyncio.create_task(bot.start_polling())
        logger.info("Started Telegram Bot polling background task.")
    else:
        logger.warning("No valid TELEGRAM_BOT_TOKEN provided. Bot is disabled.")

async def cleanup_background_bot(app: web.Application):
    bot = app.get("tg_bot")
    if bot:
        bot.stop()
    bot_task = app.get("bot_task")
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
    logger.info("Cleaned up Telegram Bot background task.")

def create_app() -> web.Application:
    app = web.Application()

    # Route preflight
    app.router.add_options("/{path:.*}", handle_cors_preflight)

    # Core Routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/book", handle_book_info)
    app.router.add_get("/api/pdf", handle_pdf)

    # Static assets
    app.router.add_static("/static/", path=FRONTEND_DIR, name="static")

    # Bot lifecycle
    app.on_startup.append(start_background_bot)
    app.on_cleanup.append(cleanup_background_bot)

    return app

if __name__ == "__main__":
    app = create_app()
    logger.info(f"Starting server on http://{HOST}:{PORT}")
    web.run_app(app, host=HOST, port=PORT)
