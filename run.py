#!/usr/bin/env python3
"""
Mawlid an-Nabiy (Мавлид ан-Набий) - Telegram Mini App & Bot Launcher
Runs the aiohttp WebApp server and the background Telegram Bot polling loop.
"""

import os
import sys
import logging

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from aiohttp import web
from dotenv import load_dotenv

# Ensure root directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv()

from backend.server import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("main")

def print_banner(host: str, port: int, webapp_url: str, bot_token: str):
    print("=" * 64)
    print("  📖  МАВЛИД АН-НАБИЙ — TELEGRAM MINI APP & EREADER BOT")
    print("=" * 64)
    print(f"  • Local WebApp URL:   http://localhost:{port}")
    print(f"  • Configured TMA URL: {webapp_url}")
    print(f"  • Telegram Bot:       @mavlidannabiybot")
    print("=" * 64)
    print("  💡 TELEGRAM MINI APP DEPLOYMENT NOTE:")
    print("  Telegram WebApps require an HTTPS URL.")
    print("  To test directly inside Telegram on your phone:")
    print("    Option A (Cloudflare - Free, No sign-up):")
    print(f"      npx cloudflared tunnel --url http://localhost:{port}")
    print("    Option B (LocalTunnel - Free, Instant):")
    print(f"      npx localtunnel --port {port}")
    print("    Option C (ngrok):")
    print(f"      ngrok http {port}")
    print("  Then update WEBAPP_URL in your .env file with the https:// URL!")
    print("=" * 64)
    print("  Server is active. Press Ctrl+C to terminate.")
    print("=" * 64 + "\n")

def find_pdf():
    candidates = [
        os.getenv("PDF_FILE_PATH", ""),
        "mavlid.pdf",
        "Мавлид_ан-Набий_(1).pdf"
    ]
    for c in candidates:
        if c:
            p = os.path.join(BASE_DIR, c)
            if os.path.exists(p):
                return p
    for f in os.listdir(BASE_DIR):
        if f.lower().endswith(".pdf"):
            return os.path.join(BASE_DIR, f)
    return None

def main():
    pdf_path = find_pdf()
    if not pdf_path or not os.path.exists(pdf_path):
        logger.error(f"Error: No PDF file found in '{BASE_DIR}'!")
        sys.exit(1)

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    webapp_url = os.getenv("WEBAPP_URL", f"http://localhost:{port}")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    print_banner(host, port, webapp_url, bot_token)

    app = create_app()
    web.run_app(app, host=host, port=port)

if __name__ == "__main__":
    main()
