import logging
from telegram import BotCommand, Update, InputFile, BotCommandScopeChat, BotCommandScopeDefault, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, RetryAfter, TimedOut
from telegram.request import HTTPXRequest
from telegram.helpers import escape_markdown
from typing import Dict, Any
import os
import re
from dotenv import load_dotenv
import json
from datetime import datetime



# Load environment variables from the .env file
load_dotenv()

# Retrieve the bot token from the environment
BOT_TOKEN = os.getenv("BOT_TOKEN")


if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in the environment variables. Check your .env file.")


FORWARD_LIST_FILE = "forward_list.json"

# Assuming these are globally defined
USER_DATA: Dict[int, Dict[str, Any]] = {}
FORWARD_LIST: Dict[str, int] = {}

# Replace these with the user IDs of authorized users
AUTHORIZED_USERS = [1704356941, 7484493290, 265243029, 6564890289]  # Replace with actual Telegram user IDs

CHANNEL_ID = "-1002454781187"  # Example channel ID

VERIFIED_USERS_FILE = "verified_users.json"
VERIFIED_USERS = {}


USER_DATA_FILE = "user_data.json"

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

async def safe_send_photo(bot, chat_id, file_id, caption=""):
    try:
        await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
    except Exception as e:
        logger.error(f"Failed to send photo to {chat_id}: {e}")


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
            BotCommand("authorize_user", "Authorize user"),
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

async def authorize_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Authorize a user (admin-only)."""
    # Get the admin's user ID and username
    admin_id = update.effective_user.id
    admin_username = update.effective_user.username or "Unknown"
    
    # Check if the user is an admin
    if admin_id not in AUTHORIZED_USERS:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        logger.warning(f"Unauthorized access attempt by @{admin_username} (ID: {admin_id}).")
        return

    # Parse the target user ID from the command
    try:
        target_user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Usage: /authorize <user_id>")
        return

    # Check if the user is already authorized
    if target_user_id in AUTHORIZED_USERS:
        await update.message.reply_text(f"✅ User ID {target_user_id} is already authorized.")
        return

    try:
        # Fetch user details from Telegram
        target_user_chat = await context.bot.get_chat(target_user_id)
        target_username = target_user_chat.username or None
        target_first_name = target_user_chat.first_name or "Unknown"
        target_display_name = f"@{target_username}" if target_username else target_first_name

        # Authorize the user and add them to the forward list
        AUTHORIZED_USERS.add(target_user_id)
        FORWARD_LIST[target_user_id] = target_display_name  # Use user ID as the key

        await update.message.reply_text(f"✅ {target_display_name} (ID: {target_user_id}) has been authorized.")
        logger.info(f"Admin @{admin_username} (ID: {admin_id}) authorized user {target_display_name} (ID: {target_user_id}).")
    except Exception as e:
        # Log errors to a log file
        logger.error(f"Failed to authorize user ID {target_user_id}: {e}")
        await update.message.reply_text(f"❌ Failed to authorize user ID {target_user_id}. Error logged.")


def escape_markdown(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(special_chars)}])", r"\\\1", text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message, dynamically set commands, and request verification for new users."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    first_name = update.effective_user.first_name or ""
    last_name = update.effective_user.last_name or ""
    chat_id = update.effective_chat.id

    # Combine full name (handle if last_name is None)
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        full_name = "Unknown Name"

    # Record the current timestamp
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save user data locally
    USER_DATA[user_id] = {
        "username": username,
        "full_name": full_name,
        "chat_id": chat_id,
        "start_time": start_time,
    }
    save_user_data()  # Save to JSON file

    logger.info(f"Saved user: {full_name} (@{username}, ID: {user_id}, Chat ID: {chat_id}, Started at: {start_time})")

    # Check if the user is already verified
    if str(user_id) in VERIFIED_USERS:
        if username not in FORWARD_LIST:
            FORWARD_LIST[username] = chat_id
            logger.info(f"Verified user @{username} (Chat ID: {chat_id}) added to forward list.")
        await set_bot_commands(context.application, user_id=user_id, is_authorized=False)
        await update.message.reply_text("Welcome back! We are preparing your slips.")
        return

    # If user is authorized
    if user_id in AUTHORIZED_USERS:
        await set_bot_commands(context.application, user_id=user_id, is_authorized=True)
        await update.message.reply_text(
            "Welcome! You are authorized to manage this bot. Full menu enabled."
        )
        # Automatically add authorized users to the forward list
        if username not in FORWARD_LIST:
            FORWARD_LIST[username] = chat_id
            logger.info(f"Authorized user @{username} (Chat ID: {chat_id}) added to forward list.")
        return

    # Handle unauthorized users: send a verification request to authorized users
    verification_request = (
        f"🔔 *Access Request*\n"
        f"{escape_markdown(full_name)} "
        f"@{escape_markdown(username)}\n"
        f"ID: {user_id}\n\n"
        f"Approve: `/add_user {user_id}`\n"
        f"Reject: `/reject {user_id}`"
    )

    logger.debug(f"Verification message: {verification_request}")

    for auth_user_id in AUTHORIZED_USERS:
        try:
            await context.bot.send_message(
                chat_id=auth_user_id,
                text=verification_request,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"Failed to send verification request to authorized user {auth_user_id}: {e}")

    await set_bot_commands(context.application, user_id=user_id, is_authorized=False)
    await update.message.reply_text(
        "Welcome! Your access request has been sent to the admins for verification."
    )
    logger.info(f"Verification request for {full_name} (@{username}, ID: {user_id}) sent to admins.")

# Load forward list from file
def load_forward_list():
    global FORWARD_LIST
    if os.path.exists(FORWARD_LIST_FILE):
        with open(FORWARD_LIST_FILE, "r") as file:
            try:
                FORWARD_LIST = json.load(file)
                print("Forward list loaded successfully.")
            except json.JSONDecodeError:
                print("Forward list file is empty or corrupted.")
                FORWARD_LIST = {}
    else:
        FORWARD_LIST = {}


# Save forward list to file
def save_forward_list():
    with open(FORWARD_LIST_FILE, "w") as file:
        json.dump(FORWARD_LIST, file, indent=4)


async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a user to the forward list based on user ID."""
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a user ID. Example: /add_user <user_id>")
        return

    try:
        user_id = int(context.args[0])  # Extract user ID from command arguments
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric user ID.")
        return

    try:
        # Attempt to fetch user details from Telegram API
        user_details = await context.bot.get_chat(user_id)
        username = user_details.username or None
        first_name = user_details.first_name or "Unknown"
        last_name = user_details.last_name or ""
        chat_id = user_details.id

        # Combine full name
        full_name = f"{first_name} {last_name}".strip()
        display_name = f"@{username}" if username else full_name

        # Save user details in USER_DATA
        USER_DATA[user_id] = {
            "username": username,
            "full_name": full_name,
            "chat_id": chat_id,
            "user_id": chat_id
        }
        save_user_data()  # Persist updated user data
    except Exception as e:
        # Handle cases where `getChat` fails
        logger.error(f"Error fetching details for user ID {user_id}: {e}")

        # Fallback to use data from `USER_DATA`
        user_data = USER_DATA.get(user_id)
        if user_data:
            username = user_data.get("username", None)
            full_name = user_data.get("full_name", "Unknown")
            display_name = f"@{username}" if username else full_name
            chat_id = user_data.get("chat_id", user_id)
        else:
            await update.message.reply_text(f"❌ Failed to fetch or retrieve saved details for user ID {user_id}.")
            return

    # Add to FORWARD_LIST if not already present
    if user_id in FORWARD_LIST:
        await update.message.reply_text(f"⚠️ User {display_name} (ID: {user_id}) is already in the forward list.")
    else:
        FORWARD_LIST[user_id] = display_name
        await update.message.reply_text(f"✅ Added user {display_name} (ID: {user_id}) to the forward list.")
        logger.info(f"✅ Added user {display_name} (ID: {user_id}) to the forward list.")

async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the forward list with display names and their chat IDs."""

    global USER_DATA1

    if FORWARD_LIST:
        with open(USER_DATA_FILE, "r") as f:
            USER_DATA1 = json.load(f)
            logger.info("User data loaded successfully.")

        response_lines = ["Forward list:"]
        for user_id, chat_id in FORWARD_LIST.items():
            # Retrieve details from USER_DATA
            user_data = USER_DATA1.get(user_id, {})
            username = user_data.get("username", "Unknown")
            full_name = user_data.get("full_name", "Unknown User")

            # Format display name
            if username != "Unknown":
                display_name = f"@{username} ({full_name})"
            else:
                display_name = full_name

            response_lines.append(f"{full_name}: {chat_id}")

            logger.info(f"USER_DATA1: {USER_DATA1}")
            logger.info(f"USER_DATA for testing: {user_data}")

        # Send the response to the user
        await update.message.reply_text("\n".join(response_lines))
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

async def send_image_to_channel(bot: Bot, image_file_id: str, caption: str = "") -> None:
    """Send an image to the specified channel."""
    try:
        await bot.send_photo(chat_id=CHANNEL_ID, photo=image_file_id, caption=caption)
        logging.info(f"Image sent to channel {CHANNEL_ID} successfully.")
    except TelegramError as e:
        logging.error(f"Failed to send image to channel {CHANNEL_ID}: {e}")

async def send_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to send an image to the channel."""
    if not context.args:
        await update.message.reply_text("Please provide the file ID or URL of the image.")
        return

    image_file_id = context.args[0]
    caption = " ".join(context.args[1:]) if len(context.args) > 1 else "Image sent to the channel."

    await update.message.reply_text("Image sent to the channel.")


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle images sent to the bot and forward them automatically for authorized users."""

    if not update.effective_user:
        logging.warning("Received an update without an effective_user.")
        return

    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

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
        await update.message.reply_text("Image received and being forwarded!")

        # Send the image to the channel
        await send_image_to_channel(context.bot, image_file_id=file_id, caption=f"")

        logging.info(f"Image from @{username} (User ID: {user_id}) forwarded to the channel.")

        # Forward the image to authorized users in FORWARD_LIST
        for forward_username, forward_chat_id in FORWARD_LIST.items():
            try:
                logger.info(f"Forwarding image to @{forward_username} (Chat ID: {forward_chat_id})")
                await safe_send_photo(
                    context.bot, 
                    forward_chat_id, 
                    file_id, 
                    # f"Forwarded image from @{username}"
                )
            except Exception as e:
                logger.error(f"Failed to forward image to @{forward_username} (Chat ID: {forward_chat_id}): {e}")

        logger.info(f"Image sent by @{username} (User ID: {user_id}) forwarded successfully.")


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

    await send_image_to_channel(context.bot, image_file_id=image_file_id, caption="")
    await update.message.reply_text("Image sent to the channel.")
    await update.message.reply_text("Image sent successfully.")


def save_user_data():
    """Save USER_DATA to a JSON file without overwriting existing data."""
    global USER_DATA
    try:
        # Check if the file exists and load existing data
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, "r") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = {}  # Handle empty or corrupted files
            USER_DATA.update(existing_data)  # Merge existing data with current USER_DATA

        # Save updated USER_DATA back to the file
        with open(USER_DATA_FILE, "w") as f:
            json.dump(USER_DATA, f, indent=4)

        logger.info(f"User data saved successfully. Total users: {len(USER_DATA)}")
        logger.debug(f"Before save, USER_DATA: {USER_DATA}")
        logger.debug(f"Existing data in file: {existing_data}")

    except Exception as e:
        logger.error(f"Failed to save user data: {e}")

def load_user_data():
    """Load USER_DATA from a JSON file."""
    global USER_DATA, FORWARD_LIST
    try:
        with open(USER_DATA_FILE, "r") as f:
            USER_DATA = json.load(f)
        logger.info("User data loaded successfully.")

        # Add all users from USER_DATA to FORWARD_LIST
        for user_id, data in USER_DATA.items():
            username = data.get("username", None) or f"User_{user_id}"  # Use a fallback if no username
            full_name = data.get("full_name", None)
            chat_id = data.get("chat_id", None)
            if chat_id and username not in FORWARD_LIST:
                FORWARD_LIST[user_id] = chat_id
                logger.info(f"Loaded user {username} (ID: {user_id}, Chat ID: {chat_id}) to forward list.")
    except FileNotFoundError:
        logger.warning(f"No existing {USER_DATA_FILE} found. Starting fresh.")
        USER_DATA = {}
    except Exception as e:
        logger.error(f"Failed to load user data: {e}")
        USER_DATA = {}

def load_verified_users():
    """Load verified users from a JSON file."""
    global VERIFIED_USERS
    if os.path.exists(VERIFIED_USERS_FILE):
        with open(VERIFIED_USERS_FILE, "r") as file:
            VERIFIED_USERS = json.load(file)
            logger.info("Verified users loaded successfully.")
    else:
        VERIFIED_USERS = {}
        logger.info("No verified users file found. Starting with an empty list.")

def save_verified_users():
    """Save verified users to a JSON file."""
    with open(VERIFIED_USERS_FILE, "w") as file:
        json.dump(VERIFIED_USERS, file, indent=4)
    logger.info("Verified users saved successfully.")

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approve a user and add them to the forward list."""
    if not context.args:
        await update.message.reply_text("Please provide a user ID. Example: /approve <user_id>")
        return
    
    user_id = context.args[0]
    if user_id in VERIFIED_USERS:
        await update.message.reply_text(f"User {user_id} is already verified.")
        return
    
    # Check if user exists in USER_DATA
    user_details = USER_DATA.get(int(user_id))
    if not user_details:
        await update.message.reply_text("User ID not found. Ensure they have started the bot.")
        return

    username = user_details["username"]
    chat_id = user_details["chat_id"]

    # Add user to VERIFIED_USERS and FORWARD_LIST
    VERIFIED_USERS[user_id] = {"username": username, "chat_id": chat_id}
    FORWARD_LIST[username] = chat_id
    save_verified_users()
    save_forward_list()  # Persist the list to file

    await update.message.reply_text(f"User @{username} (ID: {user_id}) has been approved and added to the forward list.")
    logger.info(f"User @{username} (ID: {user_id}) approved by {update.effective_user.username}.")

async def reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reject a user's verification request."""
    if not context.args:
        await update.message.reply_text("Please provide a user ID. Example: /reject <user_id>")
        return
    
    user_id = context.args[0]
    if user_id in USER_DATA:
        del USER_DATA[int(user_id)]
    await update.message.reply_text(f"User ID {user_id} has been rejected.")
    logger.info(f"User ID {user_id} rejected by {update.effective_user.username}.")


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
    application.add_handler(CommandHandler("approve", approve_user))
    application.add_handler(CommandHandler("reject", reject_user))
    # Add the `/authorize` command
    application.add_handler(CommandHandler("authorize", authorize_user))


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

        load_verified_users()
        save_user_data()
        load_user_data()

        # Retrieve or create the event loop
        loop = asyncio.get_event_loop()
        
        loop.run_until_complete(main())
    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")