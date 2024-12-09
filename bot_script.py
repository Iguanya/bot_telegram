import logging
from telegram import BotCommand, Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# Replace with your bot token
BOT_TOKEN = '7425198155:AAHdA02heNdgiXIQ5oyV5RZhlA1THX1m44I'

# Dictionary to store Telegram usernames and their corresponding chat IDs
FORWARD_LIST = {}

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def set_bot_commands(application) -> None:
    """Set up persistent bot menu commands."""
    commands = [
        BotCommand("start", "Start the bot and display the menu"),
        BotCommand("add_user", "Add a username to the forward list"),
        BotCommand("show_users", "Show all usernames in the forward list"),
        BotCommand("remove_user", "Remove a username from the forward list"),
        BotCommand("clear_users", "Clear the forward list"),
        BotCommand("send_image", "Manually send an image to the forward list"),  # New command
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message."""
    logger.info(f"User {update.effective_user.username or update.effective_user.id} started the bot.")
    await update.message.reply_text(
        "Welcome to the bot! Use the commands to manage forwarding settings."
    )
    await update.message.reply_text("Welcome! Please send an image.")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a username to the forward list."""
    username = context.args[0] if context.args else None
    if not username:
        await update.message.reply_text("Please provide a username. Example: /add_user username")
        return

    if username.startswith("@"):
        username = username[1:]  # Remove '@'

    user_id = update.message.chat.id  # Get user's chat ID
    # Store user's chat ID in FORWARD_LIST
    FORWARD_LIST[username] = user_id

    await update.message.reply_text(f"Added @{username} to the forward list.")
    logger.info(f"Added @{username} with chat ID {user_id} to the forward list.")

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the forward list with usernames and their chat IDs."""
    if FORWARD_LIST:
        response = "Forward list:\n" + "\n".join(f"@{username}: {user_id}" for username, user_id in FORWARD_LIST.items())
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("The forward list is empty.")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a username from the forward list."""
    username = context.args[0] if context.args else None
    if not username:
        await update.message.reply_text("Please provide a username. Example: /remove_user username")
        return

    if username.startswith("@"):
        username = username[1:]  # Remove '@' if provided

    if username in FORWARD_LIST:
        del FORWARD_LIST[username]
        await update.message.reply_text(f"Removed @{username} from the forward list.")
        logger.info(f"Removed @{username} from the forward list.")
    else:
        await update.message.reply_text(f"Username @{username} is not in the forward list.")

async def clear_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all usernames from the forward list."""
    FORWARD_LIST.clear()
    await update.message.reply_text("Cleared the forward list.")
    logger.info("Cleared the forward list.")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle received images and forward them."""
    if update.message.photo:
        sender = update.message.chat.username or update.message.chat.id
        logger.info(f"Received an image from {sender}")

        # Process the image to get details
        photos = update.message.photo
        largest_photo = max(photos, key=lambda p: p.file_size)

        f_id = largest_photo.file_id
        caption = f"file_id: {f_id}"

        # Send back the image with details to the original sender
        try:
            await context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=InputFile(f_id),
                caption=caption
            )
            logger.info(f"Sent image back with details to chat {update.message.chat_id}.")
        except TelegramError as e:
            logger.error(f"Failed to send image back: {e}")

        # Forward image to users in FORWARD_LIST using their stored chat IDs
        for username, user_id in FORWARD_LIST.items():
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=f_id,
                    caption=f"Forwarded from @{sender}"
                )
                logger.info(f"Forwarded image to @{username}")
            except TelegramError as e:
                logger.error(f"Failed to forward to @{username}: {e}")

async def send_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually send an image to all users in the forward list."""
    if not FORWARD_LIST:
        await update.message.reply_text("The forward list is empty.")
        return

    # Check if an argument (image file ID or URL) is provided
    if not context.args:
        await update.message.reply_text("Please provide a file ID or URL of the image. Example: /send_image <file_id_or_url>")
        return

    image = context.args[0]  # First argument is the image file ID or URL
    caption = " ".join(context.args[1:]) if len(context.args) > 1 else "Manually sent image"

    for username in FORWARD_LIST.keys():
        try:
            user_id = FORWARD_LIST[username]  # Get user ID from FORWARD_LIST
            await context.bot.send_photo(
                chat_id=user_id,
                photo=image,
                caption=f"{caption}\n\nSent by: @{update.message.chat.username or update.message.chat.id}"
            )
            logger.info(f"Manually sent image to @{username}")
        except Exception as e:
            logger.error(f"Failed to send image to @{username}: {e}")
    
    await update.message.reply_text("Image has been sent to the forward list.")

# Function to set up bot commands
async def main() -> None:
    """Start the bot."""
    logger.info("Starting bot")
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Set bot commands
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot and display the menu"),
        BotCommand("add_user", "Add a user to forward images"),
        BotCommand("show_users", "Show the forward list"),
        BotCommand("remove_user", "Remove a user from the forward list"),
        BotCommand("clear_users", "Clear the forward list"),
        BotCommand("send_image", "Manually send an image to the forward list"), 
    ])

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_user", add_user))
    application.add_handler(CommandHandler("show_users", show_users))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("clear_users", clear_users))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(CommandHandler("send_image", send_image))

    # Start polling
    await application.run_polling()

if __name__ == "__main__":
    try:
        import asyncio
        import nest_asyncio

        # Allow nested event loops for environments where a loop is already running
        nest_asyncio.apply()

        # Retrieve or create the event loop
        loop = asyncio.get_event_loop()
        
        loop.run_until_complete(main())
    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")