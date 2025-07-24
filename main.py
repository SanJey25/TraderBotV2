import os
import json
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, CallbackQueryHandler, filters
)

# Conversation states
PROFILE_NAME, PROFILE_CONTACT = range(2)
PHOTO, ITEM_NAME, CATEGORY, DESCRIPTION, WANTED_ITEM = range(5)
EDIT_FIELD_SELECTION, EDIT_NEW_VALUE = range(10, 12)
SEARCH_TYPE, SEARCH_QUERY, SEARCH_DISPLAY = range(20, 23)

# File paths
PROFILE_FILE = "data/profiles.json"
ITEMS_FILE = "data/items.json"
os.makedirs("images", exist_ok=True)
os.makedirs("data", exist_ok=True)

for file in [PROFILE_FILE, ITEMS_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({} if "profiles" in file else [], f)

# ===== Start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    profiles = load_profiles()

    if user_id not in profiles:
        await update.message.reply_text(
            "👋 Welcome to Barter Bot!\nYou need to create a profile to continue.",
            reply_markup=ReplyKeyboardMarkup([["Create Profile"]], resize_keyboard=True)
        )
    else:
        await show_main_menu(update)

# ===== Profile Creation =====
async def create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 What is your name?", reply_markup=ReplyKeyboardRemove())
    return PROFILE_NAME

async def get_profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("📞 Now enter your contact (phone, Telegram username, etc):")
    return PROFILE_CONTACT

async def get_profile_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    name = context.user_data["name"]
    contact = update.message.text

    profiles = load_profiles()
    profiles[user_id] = {"name": name, "contact": contact}

    with open(PROFILE_FILE, "w") as f:
        json.dump(profiles, f, indent=2)

    await update.message.reply_text("✅ Profile created successfully!")
    await show_main_menu(update)
    return ConversationHandler.END

# ===== Upload Item Flow =====
async def upload_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Send a photo of the item you'd like to trade:")
    return PHOTO

async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    photo = update.message.photo[-1]
    file = await photo.get_file()
    photo_path = f"images/{user_id}_{photo.file_unique_id}.jpg"
    await file.download_to_drive(photo_path)

    context.user_data["photo"] = photo_path
    await update.message.reply_text("🔛 What is the name of the item?")
    return ITEM_NAME

async def receive_item_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("🍿 What category is it in? (e.g. football, gym, tennis, etc)")
    return CATEGORY

async def receive_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text
    await update.message.reply_text("📜 Add a short description:")
    return DESCRIPTION

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text("🎯 What item are you looking for in return?")
    return WANTED_ITEM

async def receive_wanted_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    profiles = load_profiles()

    if user_id not in profiles:
        await update.message.reply_text("❌ You must create a profile first.")
        return ConversationHandler.END

    profile = profiles[user_id]
    item = {
        "user_id": user_id,
        "photo": context.user_data["photo"],
        "name": context.user_data["name"],
        "category": context.user_data["category"],
        "description": context.user_data["description"],
        "wanted_item": update.message.text,
        "contact": profile["contact"]
    }

    with open(ITEMS_FILE, "r+") as f:
        try:
            items = json.load(f)
        except json.JSONDecodeError:
            items = []

        items.append(item)
        f.seek(0)
        f.truncate()
        json.dump(items, f, indent=2)

    await update.message.reply_text("✅ Your item has been uploaded!")
    await show_main_menu(update)
    return ConversationHandler.END

# ===== My Profile =====
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    profiles = load_profiles()

    if user_id not in profiles:
        await update.message.reply_text("❌ No profile found.")
        return

    profile = profiles[user_id]
    await update.message.reply_text(
        f"👤 *Your Profile:*\n\n"
        f"🧑 Name: {profile['name']}\n"
        f"📞 Contact: {profile['contact']}",
        parse_mode="Markdown"
    )

# ===== Main Menu =====
async def show_main_menu(update: Update):
    buttons = [
        ["My Profile", "My Items"],
        ["Search Barter Items", "Upload New Item"]
    ]
    await update.message.reply_text("📋 Main Menu:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))

# ===== Loaders =====
def load_profiles():
    with open(PROFILE_FILE, "r") as f:
        return json.load(f)

# ===== SEARCH SYSTEM =====
async def start_search(update: Update, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Common Search", callback_data="search_common")],
        [InlineKeyboardButton("📛 Search by Name", callback_data="search_name")],
        [InlineKeyboardButton("🎯 Search by Wanted Item", callback_data="search_wanted")]
    ])
    await update.message.reply_text("🔎 Choose a search type:", reply_markup=keyboard)
    return SEARCH_TYPE

async def handle_search_type(update: Update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["search_type"] = query.data
    await query.edit_message_text("💬 Send your search keyword:")
    return SEARCH_QUERY

async def perform_search(update: Update, context):
    keyword = update.message.text.lower()
    search_type = context.user_data.get("search_type")

    with open(ITEMS_FILE, "r") as f:
        try:
            items = json.load(f)
        except json.JSONDecodeError:
            items = []

    matched = []
    for item in items:
        name = item.get("name", "").lower()
        category = item.get("category", "").lower()
        description = item.get("description", "").lower()
        wanted = item.get("wanted_item", "").lower()

        if ((search_type == "search_common" and (keyword in name or keyword in category or keyword in description or keyword in wanted)) or
            (search_type == "search_name" and keyword in name) or
            (search_type == "search_wanted" and keyword in wanted)):
            matched.append(item)

    if not matched:
        await update.message.reply_text("❌ No items found.")
        return ConversationHandler.END

    context.user_data["search_results"] = matched
    context.user_data["search_index"] = 0
    return await show_next_search_result(update, context)

async def show_next_search_result(update_or_query, context):
    results = context.user_data["search_results"]
    index = context.user_data.get("search_index", 0)

    if index >= len(results):
        await update_or_query.message.reply_text("🚫 No more items found.")
        return ConversationHandler.END

    item = results[index]
    caption = (
        f"📦 *{item['name']}*\n"
        f"🏷 Category: {item['category']}\n"
        f"📝 {item['description']}\n"
        f"🎯 Wants: {item['wanted_item']}\n"
        f"📞 Contact: {item['contact']}"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Match", callback_data="search_match"),
            InlineKeyboardButton("❌ Pass", callback_data="search_pass")
        ]
    ])

    with open(item['photo'], "rb") as img:
        await update_or_query.message.reply_photo(photo=img, caption=caption, parse_mode="Markdown", reply_markup=buttons)
    return SEARCH_DISPLAY

async def handle_search_action(update: Update, context):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "search_pass":
        context.user_data["search_index"] += 1
        return await show_next_search_result(query, context)
    elif action == "search_match":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("✅ You matched with this item!")
        return ConversationHandler.END

# ===== Main Entrypoint =====
def main():
    app = ApplicationBuilder().token("7349864999:AAExOPlI1kZUVh2I4gVZziCT6OQ6XwnQeS0").build()

    profile_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(Create Profile)$"), create_profile)],
        states={
            PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_profile_name)],
            PROFILE_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_profile_contact)],
        },
        fallbacks=[]
    )

    upload_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(Upload New Item)$"), upload_item_start)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, receive_photo)],
            ITEM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_item_name)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_category)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
            WANTED_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_wanted_item)],
        },
        fallbacks=[]
    )

    search_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(Search Barter Items)$"), start_search)],
        states={
            SEARCH_TYPE: [CallbackQueryHandler(handle_search_type, pattern="^search_")],
            SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, perform_search)],
            SEARCH_DISPLAY: [CallbackQueryHandler(handle_search_action, pattern="^search_(match|pass)$")],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile_conv)
    app.add_handler(upload_conv)
    app.add_handler(search_conv)
    app.add_handler(MessageHandler(filters.Regex("^(My Profile)$"), show_profile))

    print("🤖 Bot running...", flush=True)
    app.run_polling()

if __name__ == "__main__":
    main()
