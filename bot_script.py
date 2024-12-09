import logging
from telegram import Update, ReplyKeyboardMarkup, InputFile, BotCommand
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from io import BytesIO

# Replace with your bot token
BOT_TOKEN = '7425198155:AAHdA02heNdgiXIQ5oyV5RZhlA1THX1m44I'

# List of Telegram usernames to forward images to
FORWARD_LIST = []

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def set_bot_commands(updater: Updater) -> None:
    """Set up persistent bot menu commands."""
    commands = [
        BotCommand("start", "Start the bot and display the menu"),
        BotCommand("add_user", "Add a username to the forward list"),
        BotCommand("show_users", "Show all usernames in the forward list"),
        BotCommand("remove_user", "Remove a username from the forward list"),
        BotCommand("clear_users", "Clear the forward list"),
    ]
    updater.bot.set_my_commands(commands)

def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message and display menu options."""
    logger.info(f"User @{update.effective_user.username} started the bot.")
    update.message.reply_text(
        "Welcome to the bot! Use the menu to manage forwarding settings."
    )

def add_user(update: Update, context: CallbackContext) -> None:
    """Add a username to the forward list."""
    username = context.args[0] if context.args else None
    if not username:
        update.message.reply_text("Please provide a username. Example: /add_user username")
        return

    if username.startswith("@"):
        username = username[1:]  # Remove '@' if provided

    if username in FORWARD_LIST:
        update.message.reply_text(f"Username @{username} is already in the forward list.")
    else:
        FORWARD_LIST.append(username)
        update.message.reply_text(f"Added @{username} to the forward list.")
        logger.info(f"Added @{username} to the forward list.")

def show_users(update: Update, context: CallbackContext) -> None:
    """Show the list of usernames in the forward list."""
    if FORWARD_LIST:
        update.message.reply_text("Forward list:\n" + "\n".join(f"@{u}" for u in FORWARD_LIST))
    else:
        update.message.reply_text("The forward list is empty.")

def remove_user(update: Update, context: CallbackContext) -> None:
    """Remove a username from the forward list."""
    username = context.args[0] if context.args else None
    if not username:
        update.message.reply_text("Please provide a username. Example: /remove_user username")
        return

    if username.startswith("@"):
        username = username[1:]  # Remove '@' if provided

    if username in FORWARD_LIST:
        FORWARD_LIST.remove(username)
        update.message.reply_text(f"Removed @{username} from the forward list.")
        logger.info(f"Removed @{username} from the forward list.")
    else:
        update.message.reply_text(f"Username @{username} is not in the forward list.")

def clear_users(update: Update, context: CallbackContext) -> None:
    """Clear all usernames from the forward list."""
    FORWARD_LIST.clear()
    update.message.reply_text("Cleared the forward list.")
    logger.info("Cleared the forward list.")

def handle_image(update: Update, context: CallbackContext) -> None:
    """Forward received images to the predefined list."""
    if update.message.photo:
        logger.info(f"Received an image from @{update.message.chat.username or update.message.chat.id}")
        for username in FORWARD_LIST:
            try:
                user = context.bot.get_chat(username)
                context.bot.send_photo(
                    chat_id=user.id,
                    photo=update.message.photo[-1].file_id,
                    caption=f"Forwarded from @{update.message.chat.username or update.message.chat.id}"
                )
                logger.info(f"Forwarded image to @{username}")
            except Exception as e:
                logger.error(f"Failed to forward to @{username}: {e}")
        update.message.reply_text("Image forwarded to the forward list.")

def main():
    """Start the bot."""
    logger.info("Starting bot")
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Register command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("add_user", add_user))
    dispatcher.add_handler(CommandHandler("show_users", show_users))
    dispatcher.add_handler(CommandHandler("remove_user", remove_user))
    dispatcher.add_handler(CommandHandler("clear_users", clear_users))
    dispatcher.add_handler(MessageHandler(Filters.photo, handle_image))

    # Set bot commands for the menu
    set_bot_commands(updater)

    # Start the bot
    updater.start_polling()
    logger.info("Bot is now polling")
    updater.idle()

if __name__ == "__main__":
    main()
