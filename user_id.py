import logging
from telegram import BotCommand, Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message and display the user's Telegram ID."""
    user_id = update.effective_user.id  # Get the user's ID
    await update.message.reply_text(f"Hello! Your Telegram User ID is: {user_id}")
    logger.info(f"User {update.effective_user.username or user_id} started the bot with ID {user_id}")
