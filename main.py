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

# New states for editing flow
EDIT_FIELD_SELECTION, EDIT_NEW_VALUE = range(10, 12)

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
    await update.message.reply_text("📛 What is the name of the item?")
    return ITEM_NAME

async def receive_item_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("🏷 What category is it in? (e.g. football, gym, tennis, etc)")
    return CATEGORY

async def receive_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text
    await update.message.reply_text("📝 Add a short description:")
    return DESCRIPTION

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text("🔄 What item are you looking for in return?")
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

# ===== My Items =====
async def my_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)

    with open(ITEMS_FILE, "r") as f:
        try:
            items = json.load(f)
        except json.JSONDecodeError:
            items = []

    user_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if "user_id" not in item:
            continue
        if item["user_id"] == user_id:
            user_items.append(item)

    if not user_items:
        await update.message.reply_text("🧺 You haven't uploaded any items yet.")
        return

    for idx, item in enumerate(user_items):
        text = (
            f"📦 *{item['name']}*\n"
            f"🏷 Category: {item['category']}\n"
            f"📝 {item['description']}\n"
            f"🎯 Wants: {item['wanted_item']}\n"
            f"📞 Contact: {item['contact']}"
        )

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{idx}"),
                InlineKeyboardButton("❌ Delete", callback_data=f"delete_{idx}")
            ]
        ])

        with open(item['photo'], "rb") as img:
            await update.message.reply_photo(photo=img, caption=text, parse_mode="Markdown", reply_markup=buttons)

# ===== Handle Callback Queries =====
async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)

    index = int(data.split("_")[1])
    context.user_data["edit_index"] = index

    # Show buttons for choosing what to edit
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Name", callback_data="edit_field_name"),
            InlineKeyboardButton("Category", callback_data="edit_field_category")
        ],
        [
            InlineKeyboardButton("Description", callback_data="edit_field_description"),
            InlineKeyboardButton("Wanted Item", callback_data="edit_field_wanted_item")
        ]
    ])

    await query.edit_message_caption("✏️ What would you like to edit?", reply_markup=keyboard)
    return EDIT_FIELD_SELECTION

async def handle_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field_map = {
        "edit_field_name": "name",
        "edit_field_category": "category",
        "edit_field_description": "description",
        "edit_field_wanted_item": "wanted_item"
    }

    selected_data = query.data
    field = field_map.get(selected_data)

    if not field:
        await query.message.reply_text("⚠️ Unknown field selected.")
        return ConversationHandler.END

    context.user_data["edit_field"] = field
    await query.edit_message_caption(f"✏️ Please send the new value for *{field.replace('_', ' ').title()}*:", parse_mode="Markdown")
    return EDIT_NEW_VALUE

async def receive_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    new_value = update.message.text
    index = context.user_data.get("edit_index")
    field = context.user_data.get("edit_field")

    if index is None or field is None:
        await update.message.reply_text("⚠️ No item or field selected for editing.")
        return ConversationHandler.END

    with open(ITEMS_FILE, "r+") as f:
        items = json.load(f)
        user_items = [item for item in items if item.get("user_id") == user_id]
        if 0 <= index < len(user_items):
            item_to_edit = user_items[index]
            real_index = items.index(item_to_edit)
            items[real_index][field] = new_value

            f.seek(0)
            f.truncate()
            json.dump(items, f, indent=2)

            await update.message.reply_text(f"✏️ Item {field.replace('_', ' ').title()} updated to: {new_value}")
        else:
            await update.message.reply_text("⚠️ Invalid item index.")

    context.user_data.pop("edit_index", None)
    context.user_data.pop("edit_field", None)
    await show_main_menu(update)
    return ConversationHandler.END

async def handle_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = str(query.from_user.id)

    index = int(data.split("_")[1])

    with open(ITEMS_FILE, "r+") as f:
        items = json.load(f)
        user_items = [item for item in items if item.get("user_id") == user_id]

        if 0 <= index < len(user_items):
            to_delete = user_items[index]
            items.remove(to_delete)
            f.seek(0)
            f.truncate()
            json.dump(items, f, indent=2)

            await query.message.delete()
            await query.message.reply_text("🗑 Item deleted.")
        else:
            await query.message.reply_text("⚠️ Invalid item index.")

# ===== Menu =====
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

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_edit_callback, pattern="^edit_")],
        states={
            EDIT_FIELD_SELECTION: [CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field_")],
            EDIT_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_value)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile_conv)
    app.add_handler(upload_conv)
    app.add_handler(edit_conv)
    app.add_handler(MessageHandler(filters.Regex("^(My Profile)$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex("^(My Items)$"), my_items))
    app.add_handler(CallbackQueryHandler(handle_delete_callback, pattern="^delete_"))

    print("🤖 Bot running...", flush=True)
    app.run_polling()

if __name__ == "__main__":
    main()