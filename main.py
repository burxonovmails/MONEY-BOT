import telebot
import sqlite3
from telebot import types
from datetime import datetime

# --- SOZLAMALAR ---
TOKEN = "8794088281:AAHyA9Hz9VXuLGqYdSeqIiQWuLkqCCGlahQ"
ADMIN_ID = 6247135484  # O'zingizning ID raqamingiz
REF_SUMMA = 500  
MIN_WITHDRAW = 5000 
bot = telebot.TeleBot(TOKEN)

# --- BAZA BILAN ISHLASH ---
conn = sqlite3.connect('premium_money_bot.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, name TEXT, balance INTEGER DEFAULT 0, referrer_id INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS transactions 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, method TEXT, wallet TEXT, status TEXT, date TEXT)''')
conn.commit()

# --- ASOSIY MENYU ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("👤 Kabinet"), types.KeyboardButton("💰 Pul ishlash"),
        types.KeyboardButton("💸 Pul yechish"), types.KeyboardButton("📜 Tarix"),
        types.KeyboardButton("📊 Statistika")
    )
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    name = message.from_user.first_name
    command_text = message.text.split()
    referrer_id = command_text[1] if len(command_text) > 1 else None

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        initial_balance = 6000 if user_id == ADMIN_ID else 0
        cursor.execute("INSERT INTO users (user_id, name, balance, referrer_id) VALUES (?, ?, ?, ?)",
                       (user_id, name, initial_balance, referrer_id))
        if referrer_id and str(referrer_id) != str(user_id):
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_SUMMA, referrer_id))
            try: bot.send_message(referrer_id, f"🎊 **Yangi hamkor!**\n+{REF_SUMMA} so'm bonus!")
            except: pass
        conn.commit()
        bot.send_message(user_id, f"👋 **Xush kelibsiz, {name}!**", reply_markup=main_menu(), parse_mode="Markdown")
    else:
        bot.send_message(user_id, "🏠 **Asosiy menyu**", reply_markup=main_menu(), parse_mode="Markdown")

# --- KABINET ---
@bot.message_handler(func=lambda message: message.text == "👤 Kabinet")
def cabinet(message):
    cursor.execute("SELECT balance, name FROM users WHERE user_id = ?", (message.chat.id,))
    user = cursor.fetchone()
    text = (f"👤 **PROFIL**\n━━━━━━━━━━━━\n📝 **Ism:** `{user[1]}`\n🆔 **ID:** `{message.chat.id}`\n💰 **Balans:** `{user[0]}` so'm")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- PUL YECHISH (TUGMALARNI TUZATILGAN VARIANTI) ---
@bot.message_handler(func=lambda message: message.text == "💸 Pul yechish")
def withdraw(message):
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (message.chat.id,))
    balance = cursor.fetchone()[0]
    
    if balance >= MIN_WITHDRAW:
        markup = types.InlineKeyboardMarkup()
        # Callback_data qisqartirildi va aniq qilindi
        markup.add(types.InlineKeyboardButton("🔹 CLICK", callback_data="get_Click"),
                   types.InlineKeyboardButton("🔸 PAYME", callback_data="get_Payme"))
        bot.send_message(message.chat.id, f"💰 **Balansingiz:** `{balance}` so'm\nTo'lov usulini tanlang:", parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, f"⚠️ Minimal yechish: {MIN_WITHDRAW} so'm.\nSizda: {balance} so'm.")

# TUGMA BOSILISHINI USHLASH (CALLBACK)
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    # Telegramga tugma bosilgani haqida javob qaytarish (bu qotib qolishni oldini oladi)
    bot.answer_callback_query(call.id)
    
    if call.data.startswith("get_"):
        method = call.data.split("_")[1]
        msg = bot.send_message(call.message.chat.id, f"📍 **{method}** tanlandi.\nKarta raqamingizni yuboring:")
        bot.register_next_step_handler(msg, finish_withdraw, method)

def finish_withdraw(message, method):
    wallet = message.text
    user_id = message.chat.id
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    
    if balance >= MIN_WITHDRAW:
        date = datetime.now().strftime("%d.%m.%Y | %H:%M")
        cursor.execute("INSERT INTO transactions (user_id, amount, method, wallet, status, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, balance, method, wallet, "Kutilmoqda ⏳", date))
        cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        bot.send_message(user_id, "✅ **So'rov yuborildi!**", parse_mode="Markdown")
        bot.send_message(ADMIN_ID, f"🔔 **YANGI SO'ROV**\nID: `{user_id}`\nSumma: {balance}\nKarta: `{wallet}`")
    else:
        bot.send_message(user_id, "❌ Balans yetarli emas.")

# --- QOLGAN FUNKSIYALAR ---
@bot.message_handler(func=lambda message: message.text == "💰 Pul ishlash")
def earn(message):
    bot_user = bot.get_me().username
    bot.send_message(message.chat.id, f"🔗 Havolangiz:\n`https://t.me/{bot_user}?start={message.chat.id}`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "📜 Tarix")
def history(message):
    cursor.execute("SELECT amount, method, status, date FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 5", (message.chat.id,))
    rows = cursor.fetchall()
    text = "📜 **TARIX:**\n"
    for r in rows: text += f"💰 {r[0]} | {r[2]}\n"
    bot.send_message(message.chat.id, text if rows else "Tarix bo'sh.")

@bot.message_handler(commands=['pay'])
def admin_pay(message):
    if message.chat.id == ADMIN_ID:
        try:
            _, tid, amt = message.text.split()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, tid))
            conn.commit()
            bot.send_message(ADMIN_ID, "✅ Bajarildi")
        except: bot.send_message(ADMIN_ID, "Xato!")

print("Bot qayta yuklandi va tayyor!")
bot.infinity_polling()
