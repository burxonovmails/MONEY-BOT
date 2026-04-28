import telebot
import sqlite3
from telebot import types
from datetime import datetime
import os
from flask import Flask
from threading import Thread

# --- RENDER UCHUN VEB SERVER (BOTNI UYG'OQ TUTISH) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is live and running!"

def run():
    # Render avtomatik beradigan PORT dan foydalanamiz
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True # Bot to'xtaganda server ham to'xtashi uchun
    t.start()

# --- SOZLAMALAR ---
# ⚠️ O'zingizning TOKEN va ADMIN_ID ni yozing!
TOKEN = "8794088281:AAHyA9Hz9VXuLGqYdSeqIiQWuLkqCCGlahQ" 
ADMIN_ID = 6247135484
REF_SUMMA = 500  
MIN_WITHDRAW = 5000 

bot = telebot.TeleBot(TOKEN)

# --- MA'LUMOTLAR BAZASI ---
def get_db_connection():
    conn = sqlite3.connect('premium_money_bot.db', check_same_thread=False)
    return conn

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, name TEXT, balance INTEGER DEFAULT 0, referrer_id INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS transactions 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, method TEXT, wallet TEXT, status TEXT, date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY)''')
conn.commit()

# --- YORDAMCHI FUNKSIYALAR ---
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

# --- KOMANDALAR VA HANDLERLAR ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    name = message.from_user.first_name
    
    # 1. Majburiy obunani tekshirish (Start bosilishi bilan)
    if not check_sub(user_id):
        text = "👋 **Xush kelibsiz!**\n\nBotdan foydalanish uchun homiy kanallarimizga a'zo bo'ling va **✅ Tekshirish** tugmasini bosing:"
        bot.send_message(user_id, text, reply_markup=sub_markup(), parse_mode="Markdown")
        return

    # 2. Referal va Ro'yxatdan o'tish tekshiruvi
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    existing_user = cursor.fetchone()

    if existing_user is None:
        # Bu yangi foydalanuvchi
        args = message.text.split()
        referrer_id = None
        
        if len(args) > 1:
            referrer_id = args[1]
            # O'zini o'zi taklif qilmaslik va taklif qilgan odam bazada borligini tekshirish
            if str(referrer_id) != str(user_id):
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_SUMMA, referrer_id))
                try:
                    bot.send_message(referrer_id, f"🎊 **Yangi hamkor!**\nSizga {REF_SUMMA} so'm bonus berildi!")
                except: pass
        
        cursor.execute("INSERT INTO users (user_id, name, balance, referrer_id) VALUES (?, ?, ?, ?)", 
                       (user_id, name, 0, referrer_id))
        conn.commit()
    
    bot.send_message(user_id, f"✅ **Xush kelibsiz, {name}!**", reply_markup=main_menu())

# --- ADMIN PANEL ---
@bot.message_handler(commands=['add'])
def add_channel(message):
    if message.chat.id != ADMIN_ID: return
    try:
        ch = message.text.split()[1]
        cursor.execute("INSERT OR IGNORE INTO channels (channel_id) VALUES (?)", (ch,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ {ch} qo'shildi.")
    except: bot.send_message(ADMIN_ID, "Xato! Masalan: `/add @kanal`")

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
    bot.send_message(ADMIN_ID, f"📢 Kanallar: \n{', '.join(channels) if channels else 'Bo‘sh'}")

# --- CALLBACK ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    bot.answer_callback_query(call.id)
    user_id = call.message.chat.id
    if call.data == "check_sub":
        if check_sub(user_id):
            bot.delete_message(user_id, call.message.message_id)
            # A'zo bo'lgandan keyin foydalanuvchini bazaga qo'shish (agar bo'lmasa)
            start(call.message) 
        else:
            bot.send_message(user_id, "❌ Hali hamma kanallarga a'zo emassiz!")
    
    elif call.data.startswith("get_"):
        method = call.data.split("_")[1]
        msg = bot.send_message(user_id, f"📍 **{method}** tanlandi. Karta raqamingizni yuboring:")
        bot.register_next_step_handler(msg, finish_withdraw, method)

# --- MENYU FUNKSIYALARI ---
@bot.message_handler(func=lambda message: message.text == "👤 Kabinet")
def cabinet(message):
    if not check_sub(message.chat.id): return
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (message.chat.id,))
    balance = cursor.fetchone()[0]
    bot.send_message(message.chat.id, f"👤 **KABINET**\n\n🆔 ID: `{message.chat.id}`\n💰 Balans: `{balance}` so'm", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💰 Pul ishlash")
def earn(message):
    if not check_sub(message.chat.id): return
    bot_info = bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={message.chat.id}"
    bot.send_message(message.chat.id, f"🔗 **Referal havolangiz:**\n\n`{link}`\n\nDo'stlaringizni taklif qiling va har biri uchun {REF_SUMMA} so'mdan oling!", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💸 Pul yechish")
def withdraw(message):
    if not check_sub(message.chat.id): return
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (message.chat.id,))
    balance = cursor.fetchone()[0]
    if balance >= MIN_WITHDRAW:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔹 CLICK", callback_data="get_Click"),
                   types.InlineKeyboardButton("🔸 PAYME", callback_data="get_Payme"))
        bot.send_message(message.chat.id, f"💰 Balans: {balance} so'm.\nQaysi usulda yechmoqchisiz?", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, f"⚠️ Minimal yechish miqdori: {MIN_WITHDRAW} so'm.")

def finish_withdraw(message, method):
    wallet, user_id = message.text, message.chat.id
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    if balance >= MIN_WITHDRAW:
        date = datetime.now().strftime("%d.%m.%Y | %H:%M")
        cursor.execute("INSERT INTO transactions (user_id, amount, method, wallet, status, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, balance, method, wallet, "Kutilmoqda", date))
        cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        bot.send_message(user_id, "✅ So'rov qabul qilindi!")
        bot.send_message(ADMIN_ID, f"🔔 **PUL YECHISH SO'ROVI**\nID: {user_id}\nSumma: {balance}\nKarta: {wallet}\nUsul: {method}")

# --- BOTNI ISHGA TUSHIRISH ---
if __name__ == "__main__":
    print("Bot ishlashga tayyor...")
    keep_alive() # Render portini faollashtirish
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
