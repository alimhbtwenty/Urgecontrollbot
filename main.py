from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import os
from datetime import datetime, timedelta

# وضعیت‌های مربوط به فرآیند گفتگو
ASK_NAME, ASK_RUNNING, ASK_URGE = range(3)

# کیبورد بله/خیر
yes_no_keyboard = ReplyKeyboardMarkup([["بله", "خیر"]], one_time_keyboard=True, resize_keyboard=True)

# --- خواندن یوزرها از فایل ---
user_ids = set()
if os.path.exists("users.txt"):
    with open("users.txt", "r") as f:
        for line in f:
            user_ids.add(int(line.strip()))

# تابع شروع
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id not in user_ids:
        user_ids.add(user_id)
        with open("users.txt", "a") as f:
            f.write(str(user_id) + "\n")
    await update.message.reply_text("سلام! اول از همه، اسمتو بگو:")
    return ASK_NAME

# تابع برای گرفتن اسم کاربر
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data['name'] = name
    user_id = update.effective_chat.id
    context.user_data['user_id'] = user_id  # ذخیره id کاربر برای استفاده در ادامه
    await update.message.reply_text(f"مرسی {name} جان! حالا بگو، امروز دویدی؟", reply_markup=yes_no_keyboard)
    return ASK_RUNNING

# تابع برای دریافت وضعیت دویدن
async def handle_running(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ran'] = update.message.text
    await update.message.reply_text("وسوسه داشتی؟", reply_markup=yes_no_keyboard)
    return ASK_URGE

# تابع برای دریافت وضعیت وسوسه
async def handle_urge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['urge'] = update.message.text.strip()
    ran = context.user_data['ran']
    urge = context.user_data['urge']
    user_id = context.user_data['user_id']
    name = context.user_data['name']
    today = datetime.now().date()

    # بررسی و محاسبه استریک
    streak = 1
    try:
        with open("log.csv", "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in reversed(lines):
                uid, date_str, *_ , prev_streak = line.strip().split(",")
                if int(uid) == user_id:
                    last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if last_date == today - timedelta(days=1):
                        streak = int(prev_streak) + 1
                    break
    except FileNotFoundError:
        pass

    # ذخیره اطلاعات امروز
    with open("log.csv", "a", encoding="utf-8") as f:
        f.write(f"{user_id},{today},{ran},{urge},{streak}\n")

    await update.message.reply_text(f"ثبت شد، {name} جان!\nاستریک فعلیت: {streak} روز پشت‌سرهم!")
    return ConversationHandler.END

# تابع لغو
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اوکی، بیخیال شدی فعلاً.")
    return ConversationHandler.END

# --- ارسال پیام یادآوری به همه یوزرها ---
async def send_reminder(app):
    for user_id in user_ids:
        try:
            await app.bot.send_message(chat_id=user_id, text="یادت نره امروز وضعیتتو ثبت کنی!\n/start رو بزن.")
        except Exception as e:
            print(f"خطا در ارسال پیام به {user_id}: {e}")

# --- ساخت اپلیکیشن ---
TOKEN = os.getenv("BOT_TOKEN")
app = ApplicationBuilder().token(TOKEN).build()

# --- زمان‌بندی یادآوری ---
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: asyncio.run(send_reminder(app)), "cron", hour=21, minute=0)
scheduler.start()

# --- ConversationHandler ---
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_RUNNING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_running)],
        ASK_URGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_urge)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

app.add_handler(conv_handler)
app.run_polling()
