import logging
from telegram import BotCommand, Update, InputFile, BotCommandScopeChat, BotCommandScopeDefault
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, RetryAfter, TimedOut
from telegram.request import HTTPXRequest
import json

# Replace with your bot token
BOT_TOKEN = '7425198155:AAHdA02heNdgiXIQ5oyV5RZhlA1THX1m44I'

# Dictionary to store Telegram usernames and their corresponding chat IDs
FORWARD_LIST = {}

# A dictionary to store user details in memory
USER_DATA = {}  

# Replace these with the user IDs of authorized users
AUTHORIZED_USERS = [1704356941, 7484493290]  # Replace with actual Telegram user IDs


request = HTTPXRequest(read_timeout=60)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def is_authorized(user_id: int) -> bool:
    """Check if the user is authorized."""
    return user_id in AUTHORIZED_USERS

async def safe_send_photo(bot, chat_id, photo, caption):
    """Safely send a photo with retries."""
    retries = 3
    for attempt in range(retries):
        try:
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
            return  # Exit on success
        except RetryAfter as e:
            wait_time = e.retry_after
            logger.warning(f"Rate limited. Retrying in {wait_time} seconds...")
            await asyncio.sleep(wait_time)
        except TimedOut:
            logger.error("Timed out while sending photo. Retrying...")
            await asyncio.sleep(5)  # Brief wait before retry
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break  # Exit loop on unexpected error
    logger.error(f"Failed to send photo to {chat_id} after {retries} attempts.")

async def set_bot_commands(application, user_id=None, is_authorized=False) -> None:
    """Set up bot commands based on user roles."""
    if is_authorized:
        # Commands for authorized users
        commands = [
            BotCommand("start", "Start the bot and display the menu"),
            BotCommand("add_user", "Add a username to the forward list"),
            BotCommand("show_users", "Show all usernames in the forward list"),
            BotCommand("remove_user", "Remove a username from the forward list"),
            BotCommand("clear_users", "Clear the forward list"),
            BotCommand("send_image", "Manually send an image to the forward list"),  # New command
        ]
        scope = BotCommandScopeChat(user_id)
    else:
        # Commands for public users
        commands = [
            BotCommand("start", "Start the bot and display the menu"),
        ]
        scope = BotCommandScopeChat(user_id) if user_id else BotCommandScopeDefault()

    # Apply commands for the given scope
    await application.bot.set_my_commands(commands, scope=scope)
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message and dynamically set commands."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    # Save username and chat ID
    USER_DATA[user_id] = {"username": username, "chat_id": update.effective_chat.id}
    logger.info(f"Saved user: {username} (ID: {user_id}, Chat ID: {update.effective_chat.id})")

    if user_id in AUTHORIZED_USERS:
        await set_bot_commands(context.application, user_id=user_id, is_authorized=True)
        await update.message.reply_text(
            "Welcome! You are authorized to manage this bot. Full menu enabled."
        )
    else:
        await set_bot_commands(context.application, user_id=user_id, is_authorized=False)
        await update.message.reply_text(
            "Welcome! We are preparing your images."
        )

    logger.info(f"User {username} (ID: {user_id}) started the bot.")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a username to the forward list."""
    if not context.args:
        await update.message.reply_text("Please provide a username. Example: /add_user <username>")
        return

    username = context.args[0]
    
    if username.startswith("@"):
        username = username[1:]  # Remove '@' for internal storage

    user_id = update.message.chat.id  # Get user's chat ID
    
    # Store user's chat ID in USER_DATA for future reference
    USER_DATA[user_id] = {"username": username, "chat_id": user_id}

    # Add to FORWARD_LIST if not already present
    if username in FORWARD_LIST:
        await update.message.reply_text(f"User @{username} is already in the forward list.")
    else:
        FORWARD_LIST[username] = user_id  # Store in FORWARD_LIST
        await update.message.reply_text(f"Added @{username} (Chat ID: {user_id}) to the forward list.")
        logger.info(f"Added @{username} (Chat ID: {user_id}) to the forward list.")

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
    """Handle images sent to the bot and forward them."""
    user_id = update.effective_user.id

    # Authorization check
    if not is_authorized(user_id):
        await update.message.reply_text("You are not authorized to send images.")
        logger.warning(f"Unauthorized image send attempt by {user_id}.")
        return

    if update.message.photo:
        # Get the largest photo (highest resolution)
        largest_photo = max(update.message.photo, key=lambda p: p.file_size)
        file_id = largest_photo.file_id

        # Acknowledge receipt
        await safe_send_photo(context.bot, update.message.chat_id, file_id, "Image received successfully!")

        # Forward the image to authorized users in FORWARD_LIST
        for username, forward_chat_id in FORWARD_LIST.items():
            logger.info(f"Forwarding image to @{username} (Chat ID: {forward_chat_id})")
            await safe_send_photo(context.bot, forward_chat_id, file_id, f"Forwarded image from @{update.message.chat.username}")


async def send_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually send an image to users in the forward list."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("You are not authorized to send images.")
        return

    if not FORWARD_LIST:
        await update.message.reply_text("The forward list is empty.")
        return

    if not context.args:
        await update.message.reply_text("Please provide a file ID or URL.")
        return

    image = context.args[0]
    caption = " ".join(context.args[1:]) if len(context.args) > 1 else "Image sent manually."

    for username, chat_id in FORWARD_LIST.items():
        logger.info(f"Sending image to @{username} (Chat ID: {chat_id})")
        await safe_send_photo(context.bot, chat_id, image, caption)

    await update.message.reply_text("Image sent successfully.")


def save_user_data():
    """Save user data to a JSON file and notify authorized users."""
    with open("user_data.json", "w") as file:
        json.dump(USER_DATA, file)

    # Notify authorized users about the saved user data
    for user_id in AUTHORIZED_USERS:
        if user_id in USER_DATA:
            username = USER_DATA[user_id]["username"]
            chat_id = USER_DATA[user_id]["chat_id"]
            message = f"Saved user: @{username} (ID: {user_id}, Chat ID: {chat_id})"
            # Send message to authorized users (you may need to handle exceptions here)
            try:
                application.bot.send_message(chat_id=user_id, text=message)
            except Exception as e:
                logger.error(f"Failed to send notification to authorized user {user_id}: {e}")

def load_user_data():
    """Load user data from a JSON file."""
    global USER_DATA
    try:
        with open("user_data.json", "r") as file:
            USER_DATA = json.load(file)
            logger.info("User data loaded successfully.")
    except FileNotFoundError:
        USER_DATA = {}
        logger.warning("User data file not found. Initialized empty USER_DATA.")


# Function for graceful shutdown and saving user data
async def stop_application(application):
    """Shutdown the bot gracefully, saving user data."""
    logger.info("Shutting down bot...")
    save_user_data()  # Persist data to JSON
    logger.info("User data saved.")
    await application.stop()
    logger.info("Application stopped.")

# Main function to start the bot
async def main() -> None:
    """Start the bot."""
    
    load_user_data()  # Load user data at startup
    
    logger.info("Starting bot")
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()

   # Set bot commands
    await set_bot_commands(application)

   # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_user", add_user))
    application.add_handler(CommandHandler("show_users", show_users))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("clear_users", clear_users))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(CommandHandler("send_image", send_image))

   # Register shutdown handler using post_shutdown instead of on_shutdown.
       # Register shutdown handler using post_shutdown instead of on_shutdown.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, stop_application))

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