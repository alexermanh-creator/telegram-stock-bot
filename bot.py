
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "YOUR_BOT_TOKEN"

MENU = [
    ["💰 Tài sản", "📊 Tài sản hiện có"],
    ["➕ Nạp thêm", "➖ Rút ra"],
    ["📜 Lịch sử", "📈 Biểu đồ"],
    ["🥧 Phân bổ", "💾 Backup"],
    ["♻️ Restore", "🛠 Hướng dẫn"]
]

def main_menu():
    return ReplyKeyboardMarkup(MENU, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Chào bạn 👋\nChọn chức năng bên dưới 👇",
        reply_markup=main_menu()
    )

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    if "Tài sản hiện có" in text:
        await update.message.reply_text("👉 Nhập tài sản hiện có Crypto và Stock...")

    elif "Tài sản" in text:
        await update.message.reply_text("📊 Tổng tài sản demo...")

    elif "Nạp" in text:
        await update.message.reply_text("➕ Nhập số tiền nạp...")

    elif "Rút" in text:
        await update.message.reply_text("➖ Nhập số tiền rút...")

    elif "Lịch" in text:
        await update.message.reply_text("📜 Lịch sử giao dịch...")

    elif "Biểu" in text:
        await update.message.reply_text("📈 Biểu đồ tăng trưởng...")

    elif "Phân" in text:
        await update.message.reply_text("🥧 Phân bổ danh mục...")

    elif "Backup" in text:
        await update.message.reply_text("💾 Backup dữ liệu...")

    elif "Restore" in text:
        await update.message.reply_text("♻️ Restore dữ liệu...")

    elif "Hướng" in text:
        await update.message.reply_text("🛠 Hướng dẫn sử dụng bot...")

    else:
        await update.message.reply_text(
            "❌ Lệnh không hợp lệ. Vui lòng dùng menu.",
            reply_markup=main_menu()
        )

def run():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router))
    app.run_polling()

if __name__ == "__main__":
    run()
