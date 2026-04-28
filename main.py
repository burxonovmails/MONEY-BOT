import telebot
import sqlite3
from telebot import types
from datetime import datetime

# --- SOZLAMALAR ---
TOKEN = "8794088281:AAHyA9Hz9VXuLGqYdSeqIiQWuLkqCCGlahQ"
ADMIN_ID = 6247135484 # O'zingizning ID raqamingiz
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
# Kanallar uchun yangi jadval
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
    
    # Ro'yxatdan o'tish (eski kod)
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        ref = message.text.split()[1] if len(message.text.split()) > 1 else None
        cursor.execute("INSERT INTO users (user_id, name, balance, referrer_id) VALUES (?, ?, ?, ?)", (user_id, message.from_user.first_name, 0, ref))
        if ref and str(ref) != str(user_id):
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_SUMMA, ref))
            try: bot.send_message(ref, f"🎊 Yangi hamkor! +{REF_SUMMA} so'm.")
            except: pass
        conn.commit()
    bot.send_message(user_id, "🏠 Asosiy menyu", reply_markup=main_menu())

# --- ADMIN PANEL (KANALLARNI BOSHQARISH) ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID: return
    text = "🛠 **Admin Panel**\n\n"
    text += "Kanal qo'shish: `/add @kanal`\n"
    text += "Kanalni o'chirish: `/del @kanal`\n"
    text += "Kanallar ro'yxati: `/list`"
    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_channel(message):
    if message.chat.id != ADMIN_ID: return
    try:
        ch = message.text.split()[1]
        cursor.execute("INSERT OR IGNORE INTO channels (channel_id) VALUES (?)", (ch,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ {ch} qo'shildi.")
    except: bot.send_message(ADMIN_ID, "Xato! Masalan: `/add @yuzernam`")

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

# --- CALLBACK VA BOSHQALAR ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    bot.answer_callback_query(call.id)
    if call.data == "check_sub":
        if check_sub(call.message.chat.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ Tayyor!", reply_markup=main_menu())
        else:
            bot.send_message(call.message.chat.id, "❌ Hali a'zo emassiz!")
    elif call.data.startswith("get_"):
        method = call.data.split("_")[1]
        msg = bot.send_message(call.message.chat.id, f"📍 **{method}** tanlandi. Karta raqamingizni yuboring:")
        bot.register_next_step_handler(msg, finish_withdraw, method)

# (Qolgan kabinet, withdraw va earn funksiyalari o'zgarmaydi...)
@bot.message_handler(func=lambda message: message.text == "👤 Kabinet")
def cabinet(message):
    cursor.execute("SELECT balance, name FROM users WHERE user_id = ?", (message.chat.id,))
    user = cursor.fetchone()
    bot.send_message(message.chat.id, f"👤 **PROFIL**\n🆔 ID: `{message.chat.id}`\n💰 Balans: `{user[0]}` so'm", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💰 Pul ishlash")
def earn(message):
    bot_user = bot.get_me().username
    bot.send_message(message.chat.id, f"🔗 Havolangiz:\n`https://t.me/{bot_user}?start={message.chat.id}`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💸 Pul yechish")
def withdraw(message):
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (message.chat.id,))
    balance = cursor.fetchone()[0]
    if balance >= MIN_WITHDRAW:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔹 CLICK", callback_data="get_Click"),
                   types.InlineKeyboardButton("🔸 PAYME", callback_data="get_Payme"))
        bot.send_message(message.chat.id, f"💰 Balansingiz: `{balance}` so'm", reply_markup=markup)
    else: bot.send_message(message.chat.id, f"⚠️ Kamida {MIN_WITHDRAW} so'm kerak.")

def finish_withdraw(message, method):
    wallet, user_id = message.text, message.chat.id
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    if balance >= MIN_WITHDRAW:
        cursor.execute("INSERT INTO transactions (user_id, amount, method, wallet, status, date) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, balance, method, wallet, "Kutilmoqda", datetime.now().strftime("%d.%m.%Y")))
        cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        bot.send_message(user_id, "✅ So'rov yuborildi!")
        bot.send_message(ADMIN_ID, f"🔔 Yangi so'rov! Summa: {balance}, Karta: {wallet}")

if __name__ == "__main__":
    bot.infinity_polling()
