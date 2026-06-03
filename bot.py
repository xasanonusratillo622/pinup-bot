import sqlite3
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = "8833836963:AAG7h_5tz0HFrny3glmObGfcGnhIRkBAxyo"

def db_connect():
    return sqlite3.connect("pinup.db")

def db_setup():
    con = db_connect()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            ism         TEXT,
            tel         TEXT,
            rol         TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mijoz_id    INTEGER,
            kuryer_id   INTEGER,
            lat         REAL,
            lon         REAL,
            izoh        TEXT,
            holat       TEXT DEFAULT 'yangi',
            vaqt        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()

def user_saqlash(user_id, ism, tel, rol):
    con = db_connect()
    con.execute("INSERT OR REPLACE INTO users (user_id, ism, tel, rol) VALUES (?, ?, ?, ?)",
                (user_id, ism, tel, rol))
    con.commit()
    con.close()

def user_olish(user_id):
    con = db_connect()
    cur = con.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    return row

def buyurtma_yaratish(mijoz_id, lat, lon, izoh):
    con = db_connect()
    cur = con.execute("INSERT INTO orders (mijoz_id, lat, lon, izoh, holat) VALUES (?, ?, ?, ?, 'yangi')",
                      (mijoz_id, lat, lon, izoh))
    order_id = cur.lastrowid
    con.commit()
    con.close()
    return order_id

def buyurtma_olish(order_id):
    con = db_connect()
    cur = con.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    row = cur.fetchone()
    con.close()
    return row

def buyurtma_yangilash(order_id, holat, kuryer_id=None):
    con = db_connect()
    if kuryer_id:
        con.execute("UPDATE orders SET holat=?, kuryer_id=? WHERE id=?", (holat, kuryer_id, order_id))
    else:
        con.execute("UPDATE orders SET holat=? WHERE id=?", (holat, order_id))
    con.commit()
    con.close()

def kuryerlar_olish():
    con = db_connect()
    cur = con.execute("SELECT user_id FROM users WHERE rol='kuryer'")
    rows = cur.fetchall()
    con.close()
    return [r[0] for r in rows]

def statistika_olish(user_id):
    con = db_connect()
    cur = con.execute("SELECT COUNT(*) FROM orders WHERE kuryer_id=? AND holat='yetkazildi'", (user_id,))
    count = cur.fetchone()[0]
    con.close()
    return count

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("🛒 Mijozman", callback_data="rol_mijoz")],
        [InlineKeyboardButton("🛵 Kuryerman", callback_data="rol_kuryer")],
    ]
    await update.message.reply_text(
        "👋 PinUP botiga xush kelibsiz!\n\nSiz kim ekansiz?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def rol_tanlash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rol = query.data.split("_")[1]
    ctx.user_data["rol"] = rol
    btn = KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True)
    await query.message.reply_text(
        f"✅ {'Mijoz' if rol == 'mijoz' else 'Kuryer'} sifatida kiryapsiz.\n\n"
        "📱 Telefon raqamingizni tasdiqlang:",
        reply_markup=ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)
    )

async def telefon_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tel = update.message.contact.phone_number
    rol = ctx.user_data.get("rol", "mijoz")
    ism = user.first_name or "Foydalanuvchi"
    user_saqlash(user.id, ism, tel, rol)
    await update.message.reply_text(
        f"✅ Tasdiqlandi!\n👤 Ism: {ism}\n📱 Tel: {tel}",
        reply_markup=ReplyKeyboardRemove()
    )
    if rol == "mijoz":
        await mijoz_asosiy(update, ctx)
    else:
        await kuryer_asosiy(update, ctx)

async def mijoz_asosiy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    btn = KeyboardButton("📍 Lokatsiyamni yuborish", request_location=True)
    await update.message.reply_text(
        "🏠 Uyingiz joylashuvini yuboring.\n\nKuryer to'g'ridan-to'g'ri keladi!",
        reply_markup=ReplyKeyboardMarkup([[btn]], resize_keyboard=True)
    )

async def lokatsiya_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    ctx.user_data["lokatsiya"] = {"lat": loc.latitude, "lon": loc.longitude}
    maps_link = f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
    await update.message.reply_text(
        f"📍 Lokatsiya qabul qilindi!\n🗺 {maps_link}\n\n"
        "✏️ Kirish yo'lini yozing:\nMasalan: '3-qavat, chap eshik'",
        reply_markup=ReplyKeyboardRemove()
    )
    ctx.user_data["holat"] = "izoh_kutilmoqda"

async def izoh_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("holat") != "izoh_kutilmoqda":
        return
    user = update.effective_user
    izoh = update.message.text
    loc = ctx.user_data.get("lokatsiya")
    if not loc:
        await update.message.reply_text("⚠️ Avval lokatsiyangizni yuboring.")
        return
    order_id = buyurtma_yaratish(user.id, loc["lat"], loc["lon"], izoh)
    ctx.user_data["holat"] = None
    maps_link = f"https://maps.google.com/?q={loc['lat']},{loc['lon']}"
    await update.message.reply_text(
        f"✅ Buyurtma #{order_id} qabul qilindi!\n\n"
        f"📍 Manzil: {maps_link}\n"
        f"💬 Izoh: {izoh}\n\n"
        "⏳ Kuryer tez orada yo'lga chiqadi!"
    )
    mijoz_info = user_olish(user.id)
    ism = mijoz_info[1] if mijoz_info else user.first_name
    tel = mijoz_info[2] if mijoz_info else "Noma'lum"
    await kuryer_xabar(ctx, order_id, loc, izoh, maps_link, ism, tel)

async def kuryer_xabar(ctx, order_id, loc, izoh, maps_link, ism, tel):
    nav_link = f"https://yandex.uz/maps/?rtext=~{loc['lat']},{loc['lon']}&rtt=auto"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Qabul qilaman", callback_data=f"qabul_{order_id}")],
        [InlineKeyboardButton("🗺 Yandex Navigatsiya", url=nav_link)],
    ])
    xabar = (
        f"🔔 Yangi buyurtma #{order_id}!\n\n"
        f"👤 Mijoz: {ism}\n"
        f"📱 Tel: {tel}\n"
        f"📍 Manzil: {maps_link}\n"
        f"💬 Izoh: {izoh}"
    )
    for uid in kuryerlar_olish():
        try:
            await ctx.bot.send_message(uid, xabar, reply_markup=buttons)
        except Exception:
            pass

async def kuryer_asosiy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    count = statistika_olish(user_id)
    await update.message.reply_text(
        f"🛵 Kuryer paneliga xush kelibsiz!\n\n"
        f"📦 Jami yetkazilgan: {count} ta\n\n"
        "Yangi buyurtma kelganda xabar yuboriladi."
    )

async def buyurtma_qabul(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ Qabul qilindi!")
    order_id = int(query.data.split("_")[1])
    order = buyurtma_olish(order_id)
    if not order:
        await query.edit_message_text("⚠️ Buyurtma topilmadi.")
        return
    if order[6] != "yangi":
        await query.edit_message_text("⚠️ Bu buyurtma allaqachon qabul qilingan!")
        return
    nav_link = f"https://yandex.uz/maps/?rtext=~{order[3]},{order[4]}&rtt=auto"
    buyurtma_yangilash(order_id, "yolda", query.from_user.id)
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yetkazib berdim", callback_data=f"yetkazildi_{order_id}")],
        [InlineKeyboardButton("🗺 Navigatsiya", url=nav_link)],
    ])
    await query.edit_message_text(
        f"🛵 Buyurtma #{order_id} qabul qilindi!\n\n"
        f"💬 Izoh: {order[5]}\n"
        f"🗺 Navigatsiya: {nav_link}",
        reply_markup=buttons
    )
    try:
        await ctx.bot.send_message(
            order[1],
            f"🛵 Kuryeringiz yo'lda!\n📦 Buyurtma #{order_id}\n⏳ Tez orada yetib keladi."
        )
    except Exception:
        pass

async def yetkazildi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🎉 Barakalla!")
    order_id = int(query.data.split("_")[1])
    buyurtma_yangilash(order_id, "yetkazildi")
    order = buyurtma_olish(order_id)
    count = statistika_olish(query.from_user.id)
    await query.edit_message_text(
        f"✅ Buyurtma #{order_id} yetkazildi!\n\n"
        f"📦 Jami yetkazilgan: {count} ta\n\n"
        "Keyingi buyurtmani kutib turing! 💪"
    )
    if order:
        try:
            await ctx.bot.send_message(
                order[1],
                f"✅ Buyurtma #{order_id} yetkazildi!\nRahmat! ⭐"
            )
        except Exception:
            pass

def main():
    db_setup()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(rol_tanlash, pattern="^rol_"))
    app.add_handler(CallbackQueryHandler(buyurtma_qabul, pattern="^qabul_"))
    app.add_handler(CallbackQueryHandler(yetkazildi, pattern="^yetkazildi_"))
    app.add_handler(MessageHandler(filters.CONTACT, telefon_qabul))
    app.add_handler(MessageHandler(filters.LOCATION, lokatsiya_qabul))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, izoh_qabul))
    print("✅ PinUp bot v2 ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
