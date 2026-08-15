import os
import sys
import shutil
import re
import logging
import asyncio
import io
import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Suppress noisy HTTP polling logs from httpx and httpcore
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.INFO)

# URL regex pattern to detect URLs in user messages
URL_REGEX = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_TELEGRAM_MSG_LEN = 4000  # Safe limit under Telegram's 4096 char limit

# Allowed users configuration (comma-separated user IDs or usernames, e.g. "12345678,myusername")
ALLOWED_USERS_RAW = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = set(
    u.strip().lstrip("@").lower()
    for u in ALLOWED_USERS_RAW.split(",")
    if u.strip()
)

TELEGRAPH_ACCESS_TOKEN = None


def is_user_allowed(user) -> bool:
    """Check if a user is allowed to access the bot."""
    if not ALLOWED_USERS:
        return True  # If ALLOWED_USERS is not configured, allow everyone

    if not user:
        return False

    user_id = str(user.id)
    username = (user.username or "").lower()

    return user_id in ALLOWED_USERS or username in ALLOWED_USERS


async def check_permission(update: Update) -> bool:
    """Check permission and send error message if unauthorized."""
    if not is_user_allowed(update.effective_user):
        user_info = f"{update.effective_user.id} (@{update.effective_user.username})" if update.effective_user else "Unknown"
        logger.warning(f"Unauthorized access attempt by user {user_info}")
        if update.message:
            await update.message.reply_text(
                "⛔ **Access Denied**: You are not authorized to use this bot.",
                parse_mode="Markdown",
            )
        return False
    return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when /start is issued."""
    if not await check_permission(update):
        return

    welcome_text = (
        "👋 **Welcome to Gallery-DL Telegram Bot!**\n\n"
        "Send me any supported link (Instagram, Twitter/X, Reddit, Pinterest, Imgur, Pixiv, Danbooru, etc.), "
        "and I will extract all direct media URLs using `gallery-dl` and publish them to **Telegra.ph** for you.\n\n"
        "📌 **Usage:** Paste any URL directly into the chat!"
    )
    if update.message:
        await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help instructions."""
    if not await check_permission(update):
        return

    help_text = (
        "ℹ️ **How to use this bot:**\n\n"
        "1. Send or paste a link into the chat.\n"
        "2. The bot executes `gallery-dl --get-urls <URL>`.\n"
        "3. All extracted direct media links will be formatted and published to a **Telegra.ph** web page!"
    )
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")


import extractor

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages containing URLs."""
    if not await check_permission(update):
        return

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # Extract URLs from message
    found_urls = URL_REGEX.findall(text)
    if not found_urls:
        await update.message.reply_text(
            "⚠️ Please send a valid link starting with http:// or https://"
        )
        return

    target_url = found_urls[0]
    status_msg = await update.message.reply_text(
        f"🔍 Extracting URLs from:\n`{target_url}`...",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

    media_items, error = await extractor.extract_gallery_urls(target_url)

    if error:
        await status_msg.edit_text(
            f"❌ **Error extracting URLs:**\n`{error[:3000]}`",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        return

    if not media_items:
        await status_msg.edit_text(
            "⚠️ No URLs were found by `gallery-dl` for this link.",
            parse_mode="Markdown",
        )
        return

    extracted_urls = [item["url"] for item in media_items]
    count = len(extracted_urls)

    # Try uploading to Telegra.ph
    telegraph_url = None
    try:
        await status_msg.edit_text(
            f"🌐 Found **{count}** link(s)! Uploading to Telegra.ph...",
            parse_mode="Markdown",
        )
        telegraph_url = await extractor.upload_to_telegraph(
            title=f"Extracted {count} Links",
            extracted_urls=extracted_urls,
            target_url=target_url,
        )
    except Exception as err:
        logger.error(f"Telegraph upload failed: {err}")

    if telegraph_url:
        result_text = (
            f"✅ **Extracted {count} link(s)!**\n\n"
            f"🔗 **Telegra.ph Page:**\n{telegraph_url}"
        )
        await status_msg.edit_text(
            result_text,
            disable_web_page_preview=False,
        )
        return

    # Fallback to text message chunks if Telegra.ph fails
    header = f"✅ Found {count} link(s):\n\n"
    chunks = []
    current_chunk = header

    for url_item in extracted_urls:
        if len(current_chunk) + len(url_item) + 1 > MAX_TELEGRAM_MSG_LEN:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = ""
        current_chunk += url_item + "\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    if chunks:
        await status_msg.edit_text(
            chunks[0],
            disable_web_page_preview=True,
        )
        for chunk in chunks[1:]:
            if update.message:
                await update.message.reply_text(
                    chunk,
                    disable_web_page_preview=True,
                )


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is missing!")
        print("CRITICAL ERROR: BOT_TOKEN environment variable is not set.")
        print("Please set BOT_TOKEN in your environment or .env file.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Bot initialized. Starting polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
