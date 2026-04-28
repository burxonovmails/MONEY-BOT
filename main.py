import telebot
import sqlite3
from telebot import types
from datetime import datetime
import os
from flask import Flask
from threading import Thread

# --- RENDER UCHUN PORT (BOT O'CHIB QOLMASLIGI UCHUN) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is live!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- SOZLAMALAR ---
# ⚠️ TOKEN va ADMIN_ID ni o'zgartirishni unutmang!
TOKEN = "8794088281:AAHyA9Hz9VXuLGqYdSeqIiQWuLkqCCGlahQ" # BotFather bergan token
ADMIN_ID = 6247135484 # O'zingizning Telegram ID raqamingiz
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
cursor.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY)''')
conn.commit()

# --- FUNKSIYALAR ---
def get_channels():
    cursor.execute("SELECT channel_id FROM channels")
    return [row[0] for row in cursor.fetchall()]

def check_sub(user_id):
    channels = get_channels()
    if not channels: return True
    for channel in channels:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status == 'left': return False
        except: continue
    return True

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Kabinet", "💰 Pul ishlash", "💸 Pul yechish", "📜 Tarix", "📊 Statistika")
    return markup

def sub_markup():
    markup = types.InlineKeyboardMarkup()
    for ch in get_channels():
        link = ch.replace('@', '')
        markup.add(types.InlineKeyboardButton("➕ Kanalga a'zo bo'lish", url=f"https://t.me/{link}"))
    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return markup

# --- HANDLERLAR ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if not check_sub(user_id):
        bot.send_message(user_id, "⚠️ **Botdan foydalanish uchun kanallarga a'zo bo'ling!**", reply_markup=sub_markup(), parse_mode="Markdown")
        return
    
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        ref = message.text.split()[1] if len(message.text.split()) > 1 else None
        cursor.execute("INSERT INTO users (user_id, name, balance, referrer_id) VALUES (?, ?, ?, ?)", (user_id, message.from_user.first_name, 0, ref))
        if ref and str(ref) != str(user_id):
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_SUMMA, ref))
            try: bot.send_message(ref, f"🎊 **Yangi hamkor!**\n+{REF_SUMMA} so'm bonus!")
            except: pass
        conn.commit()
    bot.send_message(user_id, f"👋 Xush kelibsiz, {message.from_user.first_name}!", reply_markup=main_menu())

# --- ADMIN KOMANDALARI ---
@bot.message_handler(commands=['add'])
def add_channel(message):
    if message.chat.id != ADMIN_ID: return
    try:
        ch = message.text.split()[1]
        cursor.execute("INSERT OR IGNORE INTO channels (channel_id) VALUES (?)", (ch,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ {ch} majburiy kanallar ro'yxatiga qo'shildi.")
    except: bot.send_message(ADMIN_ID, "Xato! Masalan: `/add @kanal_nomi`")

@bot.message_handler(commands=['del'])
def del_channel(message):
    if message.chat.id != ADMIN_ID: return
    try:
        ch = message.text.split()[1]
        cursor.execute("DELETE FROM channels WHERE channel_id = ?", (ch,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"❌ {ch} o'chirildi.")
    except: bot.send_message(ADMIN_ID, "Xato!")

@bot.message_handler(commands=['list'])
def list_channels(message):
    if message.chat.id != ADMIN_ID: return
    channels = get_channels()
    bot.send_message(ADMIN_ID, f"📢 Majburiy kanallar:\n{', '.join(channels) if channels else 'Hozircha yo‘q'}")

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    bot.answer_callback_query(call.id)
    user_id = call.message.chat.id
    if call.data == "check_sub":
        if check_sub(user_id):
            bot.delete_message(user_id, call.message.message_id)
            bot.send_message(user_id, "✅ Rahmat! Endi botdan foydalanishingiz mumkin.", reply_markup=main_menu())
        else:
            bot.send_message(user_id, "❌ Hali a'zo emassiz!")
    elif call.data.startswith("get_"):
        method = call.data.split("_")[1]
        msg = bot.send_message(user_id, f"📍 **{method}** tanlandi. Karta raqamingizni yuboring:")
        bot.register_next_step_handler(msg, finish_withdraw, method)

# --- MENYU FUNKSIYALARI ---
@bot.message_handler(func=lambda message: message.text == "👤 Kabinet")
def cabinet(message):
    cursor.execute("SELECT balance, name FROM users WHERE user_id = ?", (message.chat.id,))
    user = cursor.fetchone()
    bot.send_message(message.chat.id, f"👤 **PROFIL**\n\n🆔 ID: `{message.chat.id}`\n💰 Balans: `{user[0]}` so'm", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💰 Pul ishlash")
def earn(message):
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={message.chat.id}"
    bot.send_message(message.chat.id, f"🔗 Sizning referal havolangiz:\n\n{link}\n\nHar bir taklif uchun {REF_SUMMA} so'm beriladi!")

@bot.message_handler(func=lambda message: message.text == "💸 Pul yechish")
def withdraw(message):
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (message.chat.id,))
    balance = cursor.fetchone()[0]
    if balance >= MIN_WITHDRAW:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔹 CLICK", callback_data="get_Click"),
                   types.InlineKeyboardButton("🔸 PAYME", callback_data="get_Payme"))
        bot.send_message(message.chat.id, f"💰 Balansingiz: {balance} so'm. To'lov usulini tanlang:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, f"⚠️ Minimal yechish miqdori: {MIN_WITHDRAW} so'm.")

def finish_withdraw(message, method):
    wallet = message.text
    user_id = message.chat.id
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    if balance >= MIN_WITHDRAW:
        date = datetime.now().strftime("%d.%m.%Y")
        cursor.execute("INSERT INTO transactions (user_id, amount, method, wallet, status, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, balance, method, wallet, "Kutilmoqda", date))
        cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        bot.send_message(user_id, "✅ So'rov qabul qilindi! Tez orada to'lab beriladi.")
        bot.send_message(ADMIN_ID, f"🔔 **Yangi pul yechish so'rovi!**\n\nID: {user_id}\nSumma: {balance}\nKarta: {wallet}\nUsul: {method}")

# --- BOTNI ISHGA TUSHIRISH ---
if __name__ == "__main__":
    print("Bot ishga tushdi...")
    keep_alive() # Render uchun veb-serverni yoqish
    bot.infinity_polling()
