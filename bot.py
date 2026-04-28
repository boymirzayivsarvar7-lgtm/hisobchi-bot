import asyncio
import aiosqlite
from datetime import datetime
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot ishlayapti"

def run_web():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_web).start()

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from datetime import datetime
import pytz
from google import genai
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


bot = Bot(BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

DB = "data.db"

# ================= DB =================

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            limit_amount INTEGER,
            created_date TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            category TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            amount INTEGER,
            days INTEGER,
            created_at TEXT
        )
        """)

        await db.commit()


# USER
async def add_user(uid):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (uid,)
        )
        await db.commit()


# NAME
async def get_name(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT name FROM users WHERE user_id=?", (uid,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row and row[0] else None


async def set_name(uid, name):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE users SET name=? WHERE user_id=?",
            (name, uid)
        )
        await db.commit()


# LIMIT
async def set_limit(uid, amount):
    today = datetime.now().date().isoformat()
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        UPDATE users 
        SET limit_amount=?, created_date=?
        WHERE user_id=?
        """, (amount, today, uid))
        await db.commit()


async def get_limit_today(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT limit_amount, created_date FROM users WHERE user_id=?",
            (uid,)
        ) as cur:
            row = await cur.fetchone()
            if row and row[1] == datetime.now().date().isoformat():
                return row[0] if row[0] else 0
            return 0


# EXPENSE
async def add_expense(uid, amount, cat):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO expenses (user_id, amount, category) VALUES (?, ?, ?)",
            (uid, amount, cat)
        )
        await db.commit()


async def get_total_today(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("""
        SELECT SUM(amount) FROM expenses
        WHERE user_id=? AND DATE(created_at)=DATE('now')
        """, (uid,)) as cur:
            r = await cur.fetchone()
            return r[0] if r and r[0] else 0


async def get_history(uid, days):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(f"""
        SELECT amount, category
        FROM expenses
        WHERE user_id=? AND created_at >= datetime('now','-{days} days')
        """, (uid,)) as cur:
            return await cur.fetchall()

# 🔥 HAFTALIK ANALIZ
async def get_weekly_stats(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE user_id=? AND created_at >= datetime('now','-7 days')
        GROUP BY category
        """, (uid,)) as cur:
            return await cur.fetchall()

# 🔥 ENG KO‘P KUN
async def get_top_day(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("""
        SELECT DATE(created_at), SUM(amount)
        FROM expenses
        WHERE user_id=? AND created_at >= datetime('now','-7 days')
        GROUP BY DATE(created_at)
        ORDER BY SUM(amount) DESC
        LIMIT 1
        """, (uid,)) as cur:
            return await cur.fetchone()


# 🔥 O‘RTACHA
async def get_average(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("""
        SELECT SUM(amount)/7
        FROM expenses
        WHERE user_id=? AND created_at >= datetime('now','-7 days')
        """, (uid,)) as cur:
            r = await cur.fetchone()
            return int(r[0]) if r and r[0] else 0


# 🔥 TREND (3 kun vs 3 kun)
async def get_trend(uid):
    async with aiosqlite.connect(DB) as db:

        # oxirgi 3 kun
        async with db.execute("""
        SELECT SUM(amount)
        FROM expenses
        WHERE user_id=? AND created_at >= datetime('now','-3 days')
        """, (uid,)) as cur:
            last = (await cur.fetchone())[0] or 0

        # oldingi 3 kun
        async with db.execute("""
        SELECT SUM(amount)
        FROM expenses
        WHERE user_id=? 
        AND created_at >= datetime('now','-6 days')
        AND created_at < datetime('now','-3 days')
        """, (uid,)) as cur:
            prev = (await cur.fetchone())[0] or 0

        if prev == 0:
            return "➖ O‘zgarish yo‘q"

        diff = int(((last - prev) / prev) * 100)

        if diff > 0:
            return f"📈 Oshgan (+{diff}%)"
        elif diff < 0:
            return f"📉 Kamaygan ({diff}%)"
        else:
            return "➖ O‘zgarish yo‘q"

# GOAL
async def set_goal(uid, name, amount, days):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO goals VALUES (?, ?, ?, ?, ?)",
            (uid, name, amount, days, now)
        )
        await db.commit()


async def get_goal(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT name, amount, days, created_at FROM goals WHERE user_id=?",
            (uid,)
        ) as cur:
            return await cur.fetchone()


# ================= AI =================

async def ai_detect(text):
    try:
        prompt = f"""
Sen klassifikatorsan.

Faqat quyidagilardan birini qaytar:
Ovqat
Transport
Xarid
Boshqa

Faqat bitta so‘z yoz. Hech qanday izoh yozma.

Matn: {text}
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        return response.text.strip().lower()

    except Exception as e:
        print("AI ERROR:", e)
        return "boshqa"

# ================= UI =================

def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Xarajat"), KeyboardButton(text="📊 Hisobot")],
            [KeyboardButton(text="⚙️ Limit"), KeyboardButton(text="🎯 Maqsad")],
            [KeyboardButton(text="📅 Tarix")]
        ],
        resize_keyboard=True
    )

def bar(p):
    p = min(p, 100)
    return "█"*(p//10) + "░"*(10-p//10)

def status(p):
    if p < 50: return "🟢 Zo‘r"
    elif p < 80: return "🟡 Sekinlashtiring"
    elif p <= 100: return "🟠 Limitga yaqin"
    else: return "🔴 OSHDINGIZ!"

# ================= FSM =================

class LimitState(StatesGroup):
    choose = State()
    amount = State()

class GoalState(StatesGroup):
    name = State()
    amount = State()
    days = State()
    confirm = State()

class HistoryState(StatesGroup):
    waiting = State()

class NameState(StatesGroup):
    name = State()
    confirm = State()


# ================= START =================

@router.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    await add_user(msg.from_user.id)

    name = await get_name(msg.from_user.id)

    # ❗ agar ism yo‘q bo‘lsa
    if not name:
        await msg.answer("Assalomu alaykum 👋\n\nIsmingiz kim?")
        await state.set_state(NameState.name)
        return

    # ❗ ism bor bo‘lsa tasdiqlash
    await msg.answer(f"{name}, sizmisiz?\n\n1️⃣ Ha\n2️⃣ Yo‘q")
    await state.set_state(NameState.confirm)


# ================= SAVE NAME =================

@router.message(NameState.name)
async def save_name(msg: Message, state: FSMContext):

    name = msg.text.strip()

    # ❗ validatsiya
    if not name:
        return await msg.answer("❌ Ism yozing")

    if len(name) > 20:
        return await msg.answer("❌ Ism juda uzun (max 20 ta harf)")

    await set_name(msg.from_user.id, name)

    await msg.answer(f"""
Assalomu alaykum, {name} 👋 

💰 Tejamkor botga xush kelibsiz!

Men sizga:
• Xarajatlarni hisoblash  
• Ularni tartibga solish  
• Natijani tahlil qilishda yordam beraman  

📊 Endi xarajatlaringizni nazorat qilishni boshlang
""", reply_markup=menu()) 
    await state.clear()


# ================= CONFIRM =================

@router.message(NameState.confirm)
async def confirm_name(msg: Message, state: FSMContext):

    text = msg.text.strip()

    if text in ["1", "1️⃣ Ha", "Ha", "ha"]:
        name = await get_name(msg.from_user.id)
        await msg.answer(f"""
    Assalomu alaykum, {name} 👋
    💰 Tejamkor botga xush kelibsiz!
    📌 Bu yerda siz:
    • Xarajatlaringizni yozasiz
    • Ularni tartibga solasiz
    • Natijani ko‘rib, nazorat qilasiz
    📊 Boshlash uchun pastdagi menyudan foydalaning
    """, reply_markup=menu())
        await state.clear()

    elif text in ["2", "2️⃣ Yo‘q", "Yo‘q", "yo‘q", "yo'q", "yoq"]:
        await msg.answer("Ismingiz kim?")
        await state.set_state(NameState.name)

    else:
        await msg.answer("1️⃣ Ha yoki 2️⃣ Yo‘q deb yozing")

# ================= LIMIT =================

@router.message(F.text == "⚙️ Limit")
async def ask_limit(msg: Message, state: FSMContext):
    limit = await get_limit_today(msg.from_user.id)

    if limit:
        await state.set_state(LimitState.choose)
        await msg.answer(f"""
🎯 Moliyaviy nazoratni boshlaymiz!

💰 O‘zingiz uchun kunlik limit belgilang

👇 Limitni yozing:
Masalan: 100000

📊 Hozirgi limit: {limit:,} so‘m 

Qo‘shasizmi?
1️⃣ Ha
2️⃣ Yangidan
""")
    else:
        await state.set_state(LimitState.amount)
        await msg.answer(f"""
🎯 Moliyaviy nazoratni boshlaymiz!

💰 Kunlik xarajat limitingizni belgilang

👇 Limitni kiriting:
Masalan: 100000 so‘m
""") 

@router.message(LimitState.choose)
async def choose(msg: Message, state: FSMContext):
    if msg.text == "1":
        await state.update_data(mode="add")
    elif msg.text == "2":
        await state.update_data(mode="new")
    else:
        return await msg.answer("1 yoki 2")

    await state.set_state(LimitState.amount)
    await msg.answer("Summani yozing:")

@router.message(LimitState.amount)
async def save_limit(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("❌ Raqam yozing")

    amount = int(msg.text)
    data = await state.get_data()
    mode = data.get("mode", "new")

    old = await get_limit_today(msg.from_user.id)
    if mode == "add":
        amount += old

    await set_limit(msg.from_user.id, amount)
    await state.clear()

    await msg.answer(f"""
╔════════════╗
 ⚙️ LIMIT SET
╚════════════╝

💰 {amount:,}
🔥 Nazorat boshlandi
""")

# ================= REPORT =================

@router.message(F.text == "📊 Hisobot")
async def report(msg: Message):
    uid = msg.from_user.id

    data = await get_weekly_stats(uid)

    if not data:
        return await msg.answer("📭 Oxirgi 7 kunda xarajat yo‘q")

    total = sum(amount for _, amount in data)

    text = "📊 OXIRGI 7 KUN ANALIZ\n\n"

    # 🔥 kategoriya
    for cat, amount in data:
        p = int((amount / total) * 100)
        text += f"{cat}: {amount:,} ({p}%)\n"

    # 🔥 jami
    text += f"\n💰 Jami: {total:,}"

    # 🔥 o‘rtacha
    avg = await get_average(uid)
    text += f"\n📊 O‘rtacha: {avg:,}"

    # 🔥 eng katta kun
    top = await get_top_day(uid)
    if top:
        date, amount = top
        text += f"\n📅 Eng ko‘p kun: {amount:,} ({date})"

    # 🔥 trend
    trend = await get_trend(uid)
    text += f"\n{trend}"

    # 🔥 maslahat
    biggest = max(data, key=lambda x: x[1])[0]

    if "Ovqat" in biggest:
        advice = "🍔 Ovqat xarajatlari yuqori. Tejash mumkin."
    elif "Transport" in biggest:
        advice = "🚕 Transportni optimallashtiring."
    elif "Xarid" in biggest:
        advice = "🛍 Xaridni kamaytirish mumkin."
    else:
        advice = "📦 Xarajatlarni nazorat qiling."

    text += f"\n\n💡 {advice}"

    await msg.answer(text)

# ================= HISTORY =================

@router.message(F.text == "📅 Tarix")
async def ask_history(msg: Message, state: FSMContext):
    await state.set_state(HistoryState.waiting)
    await msg.answer("1️⃣ Bugun\n2️⃣ 7 kun\n3️⃣ 30 kun")

@router.message(HistoryState.waiting)
async def show_history(msg: Message, state: FSMContext):
    days = {"1":1,"2":7,"3":30}.get(msg.text)
    if not days:
        return await msg.answer("1/2/3")

    data = await get_history(msg.from_user.id, days)
    text = "\n".join([f"💸 {a:,} — {c}" for a,c in data]) or "yo‘q"

    await msg.answer(text)
    await state.clear()

# ================= GOAL =================

@router.message(F.text == "🎯 Maqsad")
async def goal_start(msg: Message, state: FSMContext):
    g = await get_goal(msg.from_user.id)

    if g:
        name, amount, days, created = g

        created_date = datetime.fromisoformat(created)
        passed = (datetime.now() - created_date).days
        left = max(days - passed, 0)
        progress = int((passed / days) * 100) if days else 0

        await msg.answer(f"""
╔══════════════════╗
      🎯 MAQSAD
╚══════════════════╝

📱 {name}
💰 {amount:,}
📅 {days} kun

⏳ {passed} kun o‘tdi
📉 {left} kun qoldi

{bar(progress)} {progress}%
━━━━━━━━━━━━━━━━━━
""")

        await msg.answer("Yangi maqsad boshlaymizmi?\n1️⃣ Ha\n2️⃣ Yo‘q")
        await state.set_state(GoalState.confirm)
        return

    await state.set_state(GoalState.name)
    await msg.answer("🎯 Nima maqsad? (masalan: Telefon)")


# ===== CONFIRM =====

@router.message(GoalState.confirm)
async def goal_confirm(msg: Message, state: FSMContext):

    if msg.text == "2":
        await msg.answer("❌ O‘zgarishsiz qoldi")
        await state.clear()
        return

    if msg.text == "1":
        await state.set_state(GoalState.name)
        await msg.answer("🎯 Yangi maqsad nomi?")
        return

    await msg.answer("1 yoki 2 tanlang")


# ===== STEP 1: NOM =====

@router.message(GoalState.name)
async def goal_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await state.set_state(GoalState.amount)
    await msg.answer("💰 Necha pul yig‘moqchisiz?")


# ===== STEP 2: SUMMA =====

@router.message(GoalState.amount)
async def goal_amount(msg: Message, state: FSMContext):

    if not msg.text.isdigit():
        return await msg.answer("❌ Faqat raqam yozing")

    await state.update_data(amount=int(msg.text))
    await state.set_state(GoalState.days)
    await msg.answer("📅 Necha kunda yig‘asiz?")


# ===== FINAL STEP =====

@router.message(GoalState.days)
async def goal_days(msg: Message, state: FSMContext):

    if not msg.text.isdigit():
        return await msg.answer("❌ Raqam yozing")

    data = await state.get_data()

    name = data["name"]
    amount = data["amount"]
    days = int(msg.text)

    per_day = amount // days if days else 0

    await set_goal(msg.from_user.id, name, amount, days)

    await msg.answer(f"""
╔══════════════════╗
   🎯 YANGI MAQSAD
╚══════════════════╝

📱 {name}
💰 {amount:,}
📅 {days} kun

💸 Kuniga: {per_day:,}

🚀 Boshladik!
━━━━━━━━━━━━━━━━━━
""")

    await state.clear()

# ================= EXPENSE =================

@router.message(F.text == "➕ Xarajat")
async def ask_expense(msg: Message):
    await msg.answer("""
➕ Yangi xarajat

💸 Summani va kategoriyani yozing

📂 Mavjud toifalar:
🍽 Ovqat | 🚕 Transport | 👕 Kiyim | 🎮 O‘yin

✍️ Masalan: 30000 ovqat
""") 


@router.message(lambda m: m.text and m.text.split()[0].isdigit())
async def expense(msg: Message):
    parts = msg.text.split()

    amount = int(parts[0])
    text = " ".join(parts[1:]) if len(parts) > 1 else ""
    text_lower = text.lower()


# 🔥 1. AVVAL O‘ZIMIZ TEKSHIRAMIZ
    if any(x in text_lower for x in ["osh", "manti", "choy", "non"]):
        raw = "ovqat"

    elif any(x in text_lower for x in ["taksi", "taxi", "metro"]):
        raw = "transport"

    elif any(x in text_lower for x in ["kiyim", "telefon"]):
        raw = "xarid"

    else:
        raw = await ai_detect(text)

        if not raw:
            raw = "boshqa"

        raw = raw.strip().lower().replace(".", "")

    # 🔥 3. CATEGORY
    if "ovqat" in raw:
        cat = "🍔 Ovqat"
    elif "transport" in raw:
        cat = "🚕 Transport"
    elif "xarid" in raw:
        cat = "🛍 Xarid"
    else:
        cat = "📦 Boshqa"

    # 🔥 SAVE
    await add_expense(msg.from_user.id, amount, cat)

    # 🔥 HISOB
    limit = await get_limit_today(msg.from_user.id)
    total = await get_total_today(msg.from_user.id)
    p = int((total / limit) * 100) if limit else 0

    # 🔥 JAVOB
    await msg.answer(f"💸 {amount:,} — {cat}")

    if p > 100:
        await msg.answer("💀 LIMITDAN OSHDINGIZ!")
    elif p > 80:
        await msg.answer("⚠️ Ehtiyot bo‘ling")
    else:
        await msg.answer("✅ Zo‘r ketayapsiz")

    if limit:
        await msg.answer(f"{bar(p)} {p}%\n{status(p)}")

# ================= REMINDER =================

# 🔥 USERLARNI OLISH (ENG MUHIM)
async def get_all_users():
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            return [row[0] for row in await cur.fetchall()]


async def reminder_loop(bot: Bot):
    while True:
        uz = pytz.timezone("Asia/Tashkent")
        now = datetime.now(uz)

        users = await get_all_users()

        # 🌅 TEST (ertalab eslatma)
        if now.hour == 6 and now.minute in [0]:
            for uid in users:
                try:
                    limit = await get_limit_today(uid)

                    await bot.send_message(uid, f"""
🌅 XAYRLI TONG!

💰 Bugungi limit: {limit:,}

⚙️ Limit qo‘yishni unutmang
""")
                except Exception as e:
                    print("❌ ERROR:", e)

            await asyncio.sleep(60)

        # 🌙 KUN YAKUNI (SMART)
        if now.hour == 23 and now.minute in [0]:
            for uid in users:
                try:
                    limit = await get_limit_today(uid)
                    total = await get_total_today(uid)

                    if limit == 0:
                        continue

                    p = int((total / limit) * 100)
                    qolgan = limit - total

                    # 🎯 MAQSAD
                    g = await get_goal(uid)
                    extra = ""

                    if g:
                        name, g_amount, g_days, created = g

                        created_date = datetime.fromisoformat(created)
                        passed = (datetime.now() - created_date).days

                        daily = g_amount // g_days if g_days else 0
                        saved = daily * passed
                        left = g_amount - saved

                        extra = f"""
🎯 {name}
💰 Qolgan: {left:,}
📅 {passed}/{g_days} kun
"""

                    # 💡 SMART COMMENT
                    if p < 50:
                        advice = "🔥 Zo‘r! Bugun juda yaxshi boshqardingiz!"
                    elif p < 80:
                        advice = "👍 Yaxshi, lekin tejash mumkin edi"
                    elif p <= 100:
                        advice = "⚠️ Limitga yaqinlashdingiz"
                    else:
                        advice = "💀 Juda ko‘p sarfladingiz!"

                    await bot.send_message(uid, f"""
🌙 KUN YAKUNI

💰 Limit: {limit:,}
💸 Sarflandi: {total:,}
📉 Qolgan: {qolgan:,}

{bar(p)} {p}%

{extra}
{advice}
""")

                except Exception as e:
                    print("❌ ERROR:", e)

            await asyncio.sleep(60)

        await asyncio.sleep(30)

# ================= RUN =================

async def main():
    await init_db()

    # 🔔 avtomatik eslatma ishga tushadi
    asyncio.create_task(reminder_loop(bot))

    print("🚀 WOW BOT + REMINDER ISHLADI")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
