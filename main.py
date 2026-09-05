import json
import os

import jdatetime
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
jdatetime.set_locale("fa_IR")

TOKEN = os.getenv("BOT_TOKEN")

USERS_FILE = "users.json"
PLACES_FILE = "places.json"
LAST_REPORT_FILE = "last_report.json"
LOG_FILE = "log.csv"

ACTION_IN = "ورود"
ACTION_OUT = "خروج"
BTN_IN = f"🟢 ثبت {ACTION_IN}"
BTN_OUT = f"🔴 ثبت {ACTION_OUT}"
BTN_NEW_PLACE = "➕ مکان جدید"
BTN_CANCEL = "❌ انصراف"

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

main_keyboard = ReplyKeyboardMarkup([[BTN_IN, BTN_OUT]], resize_keyboard=True)


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


users = load_json(USERS_FILE)
places = load_json(PLACES_FILE)  # chat_id -> [place, ...]
last_report_day = load_json(LAST_REPORT_FILE)  # chat_id -> "1405/06/14"


def to_fa_digits(s):
    return s.translate(FA_DIGITS)


def build_report(chat_id, action, place):
    now = jdatetime.datetime.now()
    today_str = now.strftime("%Y/%m/%d")
    time_str = to_fa_digits(f"{now.hour}:{now.minute:02d}")

    lines = []
    if last_report_day.get(chat_id) != today_str:
        lines += [
            "سلام",
            now.strftime("%A"),
            to_fa_digits(today_str),
        ]
        last_report_day[chat_id] = today_str
        save_json(LAST_REPORT_FILE, last_report_day)

    if action == ACTION_IN:
        lines.append(f"ورود به {place}")
    else:
        lines.append(ACTION_OUT)
    lines.append(time_str)

    return "\n".join(lines)


def places_keyboard(chat_id):
    saved = places.get(chat_id, [])
    rows = [saved[i : i + 2] for i in range(0, len(saved), 2)]
    rows.append([BTN_NEW_PLACE])
    rows.append([BTN_CANCEL])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id not in users:
        users[chat_id] = update.effective_user.first_name or "کاربر"
        save_json(USERS_FILE, users)
    context.user_data.clear()
    await update.message.reply_text(
        f"سلام {users[chat_id]} جان!\n"
        "هر وقت رسیدی یا خواستی از یه جا بری، یکی از دکمه‌های زیر رو بزن، "
        "بعدش اسم مکان رو انتخاب کن. همین!",
        reply_markup=main_keyboard,
    )


async def ask_place(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = ACTION_IN if update.message.text == BTN_IN else ACTION_OUT
    context.user_data.clear()
    context.user_data["pending_action"] = action
    chat_id = str(update.effective_chat.id)
    await update.message.reply_text(
        "کجا بودی؟ از لیست انتخاب کن یا مکان جدید اضافه کن:",
        reply_markup=places_keyboard(chat_id),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("لغو شد.", reply_markup=main_keyboard)


async def ask_new_place_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pending_action" not in context.user_data:
        await update.message.reply_text(
            "اول یکی از دکمه‌های ورود یا خروج رو بزن.", reply_markup=main_keyboard
        )
        return
    context.user_data["awaiting_new_place"] = True
    await update.message.reply_text("اسم مکان جدید رو بنویس:")


async def record_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id, action, place):
    name = users.get(chat_id, update.effective_user.first_name or "کاربر")
    now = jdatetime.datetime.now()

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{chat_id},{name},{action},{place},{now.togregorian().isoformat()}\n")

    report = build_report(chat_id, action, place)
    await update.message.reply_text(
        f"کپی کن و بفرست تو گروه:\n```\n{report}\n```",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard,
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    text = update.message.text.strip()

    if context.user_data.get("awaiting_new_place"):
        place = text
        saved = places.setdefault(chat_id, [])
        if place not in saved:
            saved.append(place)
            save_json(PLACES_FILE, places)
        action = context.user_data.pop("pending_action")
        context.user_data.pop("awaiting_new_place")
        await record_entry(update, context, chat_id, action, place)
        return

    action = context.user_data.get("pending_action")
    if action and text in places.get(chat_id, []):
        context.user_data.pop("pending_action")
        await record_entry(update, context, chat_id, action, text)
        return

    await update.message.reply_text(
        "متوجه نشدم. یکی از دکمه‌های ورود یا خروج رو بزن.", reply_markup=main_keyboard
    )


def main():
    if not TOKEN:
        raise RuntimeError("متغیر محیطی BOT_TOKEN تنظیم نشده")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_IN}$"), ask_place))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_OUT}$"), ask_place))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_NEW_PLACE}$"), ask_new_place_name))
    app.add_handler(MessageHandler(filters.Regex(f"^{BTN_CANCEL}$"), cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == "__main__":
    main()
