import json
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")  # چت/گروه همکارها که گزارش‌ها براش ارسال می‌شه

USERS_FILE = "users.json"
LOG_FILE = "log.csv"

ACTION_IN = "ورود"
ACTION_OUT = "خروج"
BTN_IN = f"🟢 ثبت {ACTION_IN}"
BTN_OUT = f"🔴 ثبت {ACTION_OUT}"
BTN_LOCATION = "📍 ارسال موقعیت مکانی"
BTN_CANCEL = "❌ انصراف"

main_keyboard = ReplyKeyboardMarkup([[BTN_IN, BTN_OUT]], resize_keyboard=True)
location_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton(BTN_LOCATION, request_location=True)], [BTN_CANCEL]],
    resize_keyboard=True,
)


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


users = load_users()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id not in users:
        users[chat_id] = update.effective_user.first_name or "کاربر"
        save_users(users)
    await update.message.reply_text(
        f"سلام {users[chat_id]} جان!\n"
        "هر وقت رسیدی یا خواستی از یه جا بری، یکی از دکمه‌های زیر رو بزن "
        "و بعدش موقعیتتو بفرست، همین!",
        reply_markup=main_keyboard,
    )


async def ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = ACTION_IN if update.message.text == BTN_IN else ACTION_OUT
    context.user_data["pending_action"] = action
    await update.message.reply_text(
        "خب، حالا دکمه لوکیشن رو بزن:", reply_markup=location_keyboard
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pending_action", None)
    await update.message.reply_text("لغو شد.", reply_markup=main_keyboard)


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.pop("pending_action", None)
    if not action:
        await update.message.reply_text(
            "اول یکی از دکمه‌های ورود یا خروج رو بزن.", reply_markup=main_keyboard
        )
        return

    chat_id = str(update.effective_chat.id)
    name = users.get(chat_id, update.effective_user.first_name or "کاربر")
    now = datetime.now()
    location = update.message.location
    lat, lon = location.latitude, location.longitude

    emoji = "🟢" if action == ACTION_IN else "🔴"
    caption = (
        f"{emoji} ثبت {action}\n"
        f"👤 {name}\n"
        f"🕒 {now.strftime('%H:%M')}   📅 {now.strftime('%Y-%m-%d')}"
    )

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{chat_id},{name},{action},{now.isoformat()},{lat},{lon}\n")

    await update.message.reply_text(f"ثبت شد ✅\n{caption}", reply_markup=main_keyboard)

    if TARGET_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=TARGET_CHAT_ID, text=caption)
            await context.bot.send_location(
                chat_id=TARGET_CHAT_ID, latitude=lat, longitude=lon
            )
        except Exception as e:
            print(f"خطا در ارسال به چت همکارها: {e}")
    else:
        print("TARGET_CHAT_ID تنظیم نشده، گزارش فقط برای خود کاربر ثبت شد.")


async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"chat id: {update.effective_chat.id}")


def main():
    if not TOKEN:
        raise RuntimeError("متغیر محیطی BOT_TOKEN تنظیم نشده")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chatid", get_chat_id))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_IN}$"), ask_location))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_OUT}$"), ask_location))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_CANCEL}$"), cancel))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    app.run_polling()


if __name__ == "__main__":
    main()
