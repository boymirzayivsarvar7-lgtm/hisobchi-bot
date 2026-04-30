import asyncio
import aiosqlite
import os
import pytz
import logging
import threading
import re
from datetime import datetime, timedelta
from flask import Flask
from google import genai

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardRemove, BotCommand
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# ================= SERVER (KEEP-ALIVE) =================
# Bot o'chib qolmasligi uchun Flask server
app = Flask(__name__)
@app.route('/')
def home(): return "Tejamkor Bot ishlamoqda..."

def run_web():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_web, daemon=True).start()

# ================= KONFIGURATSIYA =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = "AIzaSyCXhBTmzy2sICOqKR0KKdy20utprciWYXs"
ADMIN_ID = 8088975078

client = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)
DB = "data.db"

# ================= GLOBAL LUG'AT (UZ, RU, EN) =================
# Har bir til uchun alohida va to'liq javoblar
texts = {
    "uz": {
        "start_lang": "╔══════════════════╗\n   🌍 TEJAMKOR BOT\n╚══════════════════╝\n\n🇺🇿 Assalomu alaykum!\n💸 Xarajatlaringizni nazorat qiling\n\n🇷🇺 Добро пожаловать!\n💸 Контролируйте свои расходы\n\n🇬🇧 Welcome!\n💸 Take control of your expenses\n\n━━━━━━━━━━━━━━━━━━\n\n👇 Tilni tanlang\n👇 Выберите язык\n👇 Choose language",
        "ask_name": "Iltimos ismingizni yozing 🙂\nMasalan: Sarvar",
        "confirm_user": "<b>{name}</b> sizmisiz? 👋",
        "welcome": "👋 Assalomu alaykum, {name}!\n\n💰 <b>Tejamkor</b> botga xush kelibsiz!\n📌 Bu yerda siz:\n• Xarajat yozasiz\n• Nazorat qilasiz\n• Analiz qilasiz\n\n👇 Menyudan foydalaning",
        "btn_yes": "✅ Ha",
        "btn_no": "❌ Yo'q",
        "btn_reset": "🔄 Yangilash",
        "limit_ask": "🎯 Moliyaviy nazoratni boshlaymiz!\n\n💰 Kunlik xarajat limitingizni belgilang\n\n👇 Limitni kiriting:\nMasalan: 100000 so'm",
        "limit_box": "╔════════════╗\n   BUGUNGI LIMIT 💸 \n ╚════════════╝\n\n💰 {amount}\n🔥 Nazorat boshlandi",
        "limit_exists": "🎯 Moliyaviy nazoratni boshlaymiz!\n\n💰 O‘zingiz uchun kunlik limit belgilang\n\n👇 Limitni yozing:\nMasalan: 100000\n\n📊 Hozirgi limit: {limit} so‘m \n\nQo‘shasizmi yana?",
        "expense_ask": "➕ Yangi xarajat\n\n💸 Summani va kategoriyani yozing\n\n📂 Mavjud toifalar:\n🍽 Ovqat | 🚕 Transport | 🛒 Xarid | 📦 Boshqa\n\n✍️ Masalan: 30000 ovqat",
        "goal_ask_name": "🎯 Nima maqsad?\n(masalan: Telefon)",
        "goal_ask_money": "💰 Necha pul yig'asiz?",
        "goal_ask_days": "📅 Necha kunda?",
        "history_period": "Qaysi kun malumot kerak?",
        "btn_history": ["Kechagi kun", "7 kun", "30 kun"],
        "no_expenses_7days": "📭 Oxirgi 7 kunda xarajat yo‘q",
        "report_title": "📊 <b>OXIRGI 7 KUN</b>\n\n",
        "report_total": "\n💰 Jami: {total:,}",
        "report_average": "\n📊 O‘rtacha: {avg:,}",
        "report_top_day": "\n\n📅 Eng ko‘p kun: {amount:,} ({date})",
        "advice_high_expense": "💡 {category} xarajatlari yuqori",
        "history_title": "📅 <b>TARIX ({days})</b>\n\n",
        "history_item": "💸 {amount:,} — {category} ({time})\n",
        "history_no_data": "❌ Ma'lumot topilmadi",
        "categories": ["Ovqat", "Transport", "Xarid", "Boshqa"]
    },
    "ru": {
        "start_lang": "🌐 Пожалуйста, выберите удобный для вас язык:",
        "ask_name": "Пожалуйста, введите ваше имя 🙂\nНапример: Иван",
        "confirm_user": "Вы <b>{name}</b>? 👋",
        "welcome": "👋 Здравствуйте, {name}!\n\n💰 Добро пожаловать в <b>Tejamkor</b>!\n📌 Здесь вы:\n• Пишете расходы\n• Контролируете\n• Анализируете\n\n👇 Используйте меню",
        "btn_yes": "✅ Да",
        "btn_no": "❌ Нет",
        "btn_reset": "🔄 Обновить",
        "limit_ask": "🎯 Начнем финансовый контроль!\n\n💰 Установите дневной лимит расходов\n\n👇 Введите сумму:\nНапример: 100000 сум",
        "limit_box": "╔════════════╗\n   ЛИМИТ НА СЕГОДНЯ 💸 \n ╚════════════╝\n\n💰 {amount}\n🔥 Контроль начат",
        "limit_exists": "📊 Текущий лимит: {limit} сум. Добавить еще?",
        "expense_ask": "➕ Новый расход\n\n💸 Введите сумму и категорию",
        "goal_ask_name": "🎯 Какая цель?\n(например: Телефон)",
        "goal_ask_money": "💰 Сколько денег нужно собрать?",
        "goal_ask_days": "📅 На сколько дней?",
        "history_period": "За какой период нужны данные?",
        "btn_history": ["Вчера", "7 дней", "30 дней"],
        "no_expenses_7days": "📭 Расходов за 7 дней нет",
        "report_title": "📊 <b>ПОСЛЕДНИЕ 7 ДНЕЙ</b>\n\n",
        "report_total": "\n💰 Всего: {total:,}",
        "report_average": "\n📊 Среднее: {avg:,}",
        "report_top_day": "\n\n📅 Самый активный день: {amount:,} ({date})",
        "advice_high_expense": "💡 Расходы на {category} высоки",
        "history_title": "📅 <b>ИСТОРИЯ ({days})</b>\n\n",
        "history_item": "💸 {amount:,} — {category} ({time})\n",
        "history_no_data": "❌ Данные не найдены",
        "categories": ["Еда", "Транспорт", "Покупки", "Другое"]
    },
    "en": {
        "start_lang": "🌐 Please choose a language that is convenient for you:",
        "ask_name": "Please enter your name 🙂\nExample: John",
        "confirm_user": "Are you <b>{name}</b>? 👋",
        "welcome": "👋 Hello, {name}!\n\n💰 Welcome to <b>Tejamkor</b> bot!\n📌 Here you can:\n• Track expenses\n• Control them\n• Analyze results",
        "btn_yes": "✅ Yes",
        "btn_no": "❌ No",
        "btn_reset": "🔄 Reset",
        "limit_ask"
        "limit_ask": "🎯 Let’s start controlling your finances!\n\n💰 Set your daily expense limit\n\n👇 Enter the amount:\nExample: 100000 UZS",
        "limit_box": "╔════════════╗\n   TODAY'S LIMIT 💸 \n ╚════════════╝\n\n💰 {amount}\n🔥 Control started",
        "limit_exists": "📊 Current limit: {limit}. Add more?",
        "expense_ask": "➕ New expense\n\n💸 Enter amount and category",
        "goal_ask_name": "🎯 What is the goal?\n(e.g., Phone)",
        "goal_ask_money": "💰 How much money to collect?",
        "goal_ask_days": "📅 In how many days?",
        "history_period": "Which period do you need?",
        "btn_history": ["Yesterday", "7 days", "30 days"],
        "no_expenses_7days": "📭 No expenses in 7 days",
        "report_title": "📊 <b>LAST 7 DAYS</b>\n\n",
        "report_total": "\n💰 Total: {total:,}",
        "report_average": "\n📊 Average: {avg:,}",
        "report_top_day": "\n\n📅 Top day: {amount:,} ({date})",
        "advice_high_expense": "💡 {category} expenses are high",
        "history_title": "📅 <b>HISTORY ({days})</b>\n\n",
        "history_item": "💸 {amount:,} — {category} ({time})\n",
        "history_no_data": "❌ No data found",
        "categories": ["Food", "Transport", "Shopping", "Other"]
    }
}

# Tilga qarab matnni qaytarish funksiyasi
def t(key, lang, **kwargs):
    value = texts.get(lang, texts["uz"]).get(key, key)
    if kwargs:
        return value.format(**kwargs)
    return value

def translate_category(category, lang):
    uz_cats = ["Ovqat", "Transport", "Xarid", "Boshqa"]
    translated_cats = t("categories", lang)
    try:
        idx = uz_cats.index(category)
        return translated_cats[idx]
    except ValueError:
        return category

# ================= MA'LUMOTLAR BAZASI =================
async def init_db():
    async with aiosqlite.connect(DB) as db:
        # Foydalanuvchilar (ism va til doimiy saqlanadi)
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, name TEXT, lang TEXT DEFAULT 'uz', 
            limit_amount INTEGER DEFAULT 0, created_date TEXT)""")
        
        # Xarajatlar (30 kunlik tarix bilan)
        await db.execute("""CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, 
            amount INTEGER, category TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        
        # Maqsadlar
        await db.execute("""CREATE TABLE IF NOT EXISTS goals (
            user_id INTEGER PRIMARY KEY, name TEXT, amount INTEGER, 
            days INTEGER, created_at TEXT)""")
        
        # 🔥 Avtomatik 30 kundan eski tarixni tozalash
        await db.execute("DELETE FROM expenses WHERE created_at < date('now', '-30 days')")
        await db.commit()

# Ma'lumotlarni olish uchun yordamchi funksiya
async def get_user_data(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT name, lang, limit_amount, created_date FROM users WHERE user_id=?", (uid,)) as cur:
            return await cur.fetchone()

# ================= FSM HOLATLARI =================
class UserReg(StatesGroup):
    lang = State()
    confirm = State()
    name = State()

class LimitSet(StatesGroup):
    mode = State()
    amount = State()

class GoalSet(StatesGroup):
    title = State()
    money = State()
    days = State()
    confirm_new = State()

class HistorySet(StatesGroup):
    period = State()

# ================= 2-BO‘LAK: START MANTIQI VA AUTH =================

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🇺🇿 O'zbek"),
        KeyboardButton(text="🇷🇺 Русский"),
        KeyboardButton(text="🇬🇧 English")
    )
    await msg.answer(t("start_lang", "uz"), reply_markup=kb.as_markup(resize_keyboard=True))
    await state.set_state(UserReg.lang)

@router.message(UserReg.lang)
async def process_lang(msg: Message, state: FSMContext):
    # Tilni aniqlash va saqlash
    lang_map = {"🇺🇿 O'zbek": "uz", "🇷🇺 Русский": "ru", "🇬🇧 English": "en"}
    selected_lang = lang_map.get(msg.text, "uz")
    await state.update_data(lang=selected_lang)
    
    # Bazadan foydalanuvchini ism bo'yicha tekshirish
    user_data = await get_user_data(msg.from_user.id)
    
    if user_data and user_data[0]:  # Agar ismi bazada bo'lsa
        name = user_data[0]
        # Shaffof tugmalar (Inline Keyboard)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn_yes", selected_lang), callback_data="auth_yes"),
                InlineKeyboardButton(text=t("btn_no", selected_lang), callback_data="auth_no")
            ]
        ])
        await msg.answer(t("confirm_user", selected_lang, name=name), reply_markup=kb, parse_mode="HTML")
        await state.set_state(UserReg.confirm)
    else:
        # Yangi foydalanuvchi bo'lsa ism so'raymiz
        await msg.answer(t("ask_name", selected_lang), reply_markup=ReplyKeyboardRemove())
        await state.set_state(UserReg.name)

@router.callback_query(UserReg.confirm, F.data == "auth_yes")
async def auth_yes(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    user_data = await get_user_data(call.from_user.id)
    name = user_data[0]
    
    # Tilni bazada yangilaymiz
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, call.from_user.id))
        await db.commit()
    
    await call.message.delete() # Tasdiqlash xabarini o'chirish
    await call.message.answer(t("welcome", lang, name=name), reply_markup=main_menu_kb(lang), parse_mode="HTML")
    await state.clear()

@router.callback_query(UserReg.confirm, F.data == "auth_no")
async def auth_no(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    await call.message.edit_text(t("ask_name", lang))
    await state.set_state(UserReg.name)

@router.message(UserReg.name)
async def process_name(msg: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    name = msg.text.strip()
    
    # Yangi foydalanuvchini bazaga kiritish
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, name, lang) VALUES (?, ?, ?)", 
                         (msg.from_user.id, name, lang))
        await db.commit()
    
    await msg.answer(t("welcome", lang, name=name), reply_markup=main_menu_kb(lang), parse_mode="HTML")
    await state.clear()

# ================= ASOSIY MENYU GENERATORI =================

def main_menu_kb(lang):
    # Har bir til uchun alohida tugmalar
    menu_struct = {
        "uz": [["➕ Xarajat", "📊 Hisobot"], ["⚙️ Limit", "🎯 Maqsad"], ["📅 Tarix"]],
        "ru": [["➕ Расход", "📊 Отчет"], ["⚙️ Лимит", "🎯 Цель"], ["📅 История"]],
        "en": [["➕ Expense", "📊 Report"], ["⚙️ Limit", "🎯 Goal"], ["📅 History"]]
    }
    
    current_menu = menu_struct.get(lang, menu_struct["uz"])
    builder = ReplyKeyboardBuilder()
    for row in current_menu:
        builder.row(*(KeyboardButton(text=btn) for btn in row))
    
    return builder.as_markup(resize_keyboard=True)

# ================= 3-BO‘LAK: LIMIT NAZORATI =================

# --- LIMIT TUGMASI BOSILGANDA ---
@router.message(F.text.in_(["⚙️ Limit", "⚙️ Лимит", "⚙️ Limit"]))
async def limit_main(msg: Message, state: FSMContext):
    user = await get_user_data(msg.from_user.id)
    if not user:
        return await msg.answer("❗ Iltimos /start buyrug'ini yuboring")
    name, lang, current_limit, limit_date = user[0], user[1], user[2], user[3]
    today = datetime.now().date().isoformat()
    
    # Bugun limit o'rnatilganmi tekshiramiz
    if current_limit > 0 and limit_date == today:
        # Shaffof tugmalar: Ha, Yo'q, Yangilash
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn_yes", lang), callback_data="lim_add"),
                InlineKeyboardButton(text=t("btn_no", lang), callback_data="lim_cancel"),
                InlineKeyboardButton(text=t("btn_reset", lang), callback_data="lim_reset")
            ]
        ])
        await msg.answer(t("limit_exists", lang, limit=f"{current_limit:,}"), reply_markup=kb)
    else:
        await msg.answer(t("limit_ask", lang))
        await state.set_state(LimitSet.amount)

# --- LIMIT AMALLARI (CALLBACK) ---
@router.callback_query(F.data.startswith("lim_"))
async def handle_limit_callback(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    user = await get_user_data(call.from_user.id)
    if not user:
        return await call.message.answer("❗ Iltimos /start buyrug'ini yuboring")
    lang = user[1]

    if action == "cancel":
        await call.message.delete()
        await state.clear()
        return

    if action == "reset":
        await state.update_data(mode="reset")
        await call.message.edit_text(t("limit_ask", lang))
        await state.set_state(LimitSet.amount)
    
    elif action == "add":
        await state.update_data(mode="add")
        await call.message.edit_text(t("limit_ask", lang))
        await state.set_state(LimitSet.amount)

# --- LIMITNI BAZAGA SAQLASH ---
@router.message(LimitSet.amount)
async def save_limit_value(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("❌ Raqam yozing!")

    new_amount = int(msg.text)
    data = await state.get_data()
    mode = data.get("mode", "new")
    lang = data.get("lang", "uz")
    
    today = datetime.now().date().isoformat()
    
    async with aiosqlite.connect(DB) as db:
        if mode == "add":
            await db.execute(
                "UPDATE users SET limit_amount = limit_amount + ?, created_date = ? WHERE user_id = ?",
                (new_amount, today, msg.from_user.id)
            )
        else:
            await db.execute(
                "UPDATE users SET limit_amount = ?, created_date = ? WHERE user_id = ?",
                (new_amount, today, msg.from_user.id)
            )
        await db.commit()

    # Yangilangan limitni olish
    user = await get_user_data(msg.from_user.id)
    final_limit = user[2]
    
    await msg.answer(
        t("limit_box", lang, amount=f"{final_limit:,}"),
        reply_markup=main_menu_kb(lang),
        parse_mode="HTML"
    )
    await state.clear()

# --- 00:00 DA LIMITNI TOZALASH MANTIQI (SCHEDULER) ---
async def daily_limit_reset():
    while True:
        uz_tz = pytz.timezone("Asia/Tashkent")
        now = datetime.now(uz_tz)
        
        # Agar vaqt roppa-rosa 00:00 bo'lsa
        if now.hour == 0 and now.minute == 0:
            async with aiosqlite.connect(DB) as db:
                # Faqat limitni 0 qilamiz, ism va til qoladi
                await db.execute("UPDATE users SET limit_amount = 0")
                await db.commit()
            print("🕒 Yangi kun boshlandi. Barcha limitlar 0 ga qaytarildi.")
            await asyncio.sleep(60) # Bir daqiqa kutib turamiz qayta ishlamasligi uchun
        
        await asyncio.sleep(30) # Har 30 soniyada vaqtni tekshirib turadi

# ================= 4-BO‘LAK: AQLLI XARAJAT VA AI TAHLILI =================

# --- 1. Kalit so'zlar orqali AI'siz tezkor tahlil (Tezlik uchun) ---
def quick_classify(text: str):
    text = text.lower()

    keywords = {
        "Ovqat": [
            # 🇺🇿
            "osh", "ovqat", "tushlik", "nonushta", "kechki ovqat",
            "somsa", "shashlik", "lagmon", "manti", "palov",
            "sho'rva", "kabob", "lavash", "burger", "hotdog",
            "pizza", "choy", "qahva", "kofe", "suv", "cola",
            "fanta", "pepsi", "ichimlik", "shirinlik", "tort",
            "muzqaymoq", "shokolad", "chips", "fastfood",
            "evos", "oqtepa", "kfc", "maxway",

            # 🇷🇺
            "еда", "обед", "ужин", "завтрак",
            "плов", "шашлык", "суп", "манты",
            "бургер", "пицца", "лаваш", "хотдог",
            "чай", "кофе", "вода", "кола",
            "сладости", "торт", "мороженое",
            "шоколад", "чипсы", "фастфуд",
            "поел", "покушал", "кушал",

            # 🇬🇧
            "food", "eat", "eating", "meal",
            "breakfast", "lunch", "dinner",
            "burger", "pizza", "hotdog",
            "lavash", "shawarma", "kebab",
            "coffee", "tea", "water", "cola",
            "sweets", "cake", "ice cream",
            "chocolate", "chips", "fast food"
        ],

        "Transport": [
            # 🇺🇿
            "taksi", "metro", "avtobus", "benzin", "gaz",
            "zapravka", "poyezd", "yo'l kira",

            # 🇷🇺
            "такси", "метро", "автобус", "бензин",
            "газ", "заправка", "поезд",

            # 🇬🇧
            "taxi", "bus", "metro", "fuel",
            "petrol", "train"
        ],

        "Xarid": [
            # 🇺🇿
            "kiyim", "bozor", "market", "do'kon",
            "poyabzal", "shim", "ko'ylak", "texnika",
            "xo'jalik", "sovun", "shampun",

            # 🇷🇺
            "одежда", "покупка", "магазин",
            "обувь", "техника", "шампунь",

            # 🇬🇧
            "shopping", "clothes", "store",
            "shoes", "electronics", "buy"
        ],
    }

    for category, words in keywords.items():
        if any(word in text for word in words):
            return category

    return None

# --- 2. Gemini AI orqali noma'lum xarajatni aniqlash ---
async def ai_classify(text: str):
    if not text: return "Boshqa"
    try:
        # Prompt faqat bitta so'z qaytarishini talab qiladi
        prompt = f"Kategoriyani aniqla (faqat 1 ta so'z qaytar): Ovqat, Transport, Xarid yoki Boshqa. Matn: {text}"
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        res_text = response.text.strip().capitalize()
        # Faqat ruxsat berilgan kategoriyalar qaytishini tekshiramiz
        if res_text in ["Ovqat", "Transport", "Xarid", "Boshqa"]:
            return res_text
        return "Boshqa"
    except Exception as e:
        print(f"AI Error: {e}")
        return "Boshqa"

# --- 3. Progress-bar va Vizual Statuslarni hisoblash ---
def get_visual_report(total, limit):
    if limit <= 0:
        return "⚪️ Limit belgilanmagan", "░░░░░░░░░░ 0%", 0
    
    percent = int((total / limit) * 100)
    bar_size = min(percent // 10, 10)
    progress_bar = "█" * bar_size + "░" * (10 - bar_size)
    
    if percent < 50:
        status = "🟢 Zo‘r ketayapsiz"
    elif percent < 80:
        status = "🟡 Yarmidan oshdingiz"
    elif percent <= 100:
        status = "🟠 Limitga oz qoldi!"
    else:
        status = "🔴 OSHDINGIZ!" # 100% dan oshgandagi holat
        
    return status, f"{progress_bar} {percent}%", percent

# --- 4. XARAJATLARNI QABUL QILISH ---
@router.message(lambda m: m.text and m.text.strip().split()[0].isdigit())
async def handle_expense_entry(msg: Message, state: FSMContext):
    if not msg.text:
        return

    parts = msg.text.strip().split()

    # ❗ faqat raqamdan boshlansa ishlaydi
    if not parts or not parts[0].isdigit():
        return

    user = await get_user_data(msg.from_user.id)
    if not user:
        return
    
    lang, current_limit = user[1], user[2]

    amount = int(parts[0])
    comment = " ".join(parts[1:])
    
    # 1. Keyword orqali
    category = quick_classify(comment)

    # 2. AI fallback
    if not category and comment:
        ai_result = await ai_classify(comment)

        if ai_result in ["Ovqat", "Transport", "Xarid", "Boshqa"]:
            category = ai_result
        else:
            category = "Boshqa"

    elif not comment:
        category = "Boshqa"

    # Bazaga saqlash
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO expenses (user_id, amount, category) VALUES (?, ?, ?)", 
            (msg.from_user.id, amount, category)
        )
        await db.commit()
        
        async with db.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id=? AND date(created_at)=date('now')", 
            (msg.from_user.id,)
        ) as cur:
            res = await cur.fetchone()
            total_today = res[0] or 0

    # Vizual
    status_text, p_bar, percent = get_visual_report(total_today, current_limit)
    
    icons = {
        "Ovqat": "🍔",
        "Transport": "🚕",
        "Xarid": "🛒",
        "Boshqa": "📦"
    }
    icon = icons.get(category, "📦")

    translated_category = translate_category(category, lang)

    response = (
        f"💸 {amount:,} — {icon} {translated_category}\n\n"
        f"{status_text}\n\n"
        f"{p_bar}"
    )

    # LIMIT OSHSA
    if percent > 100:
        over_text = {
            "uz": "💀 LIMITDAN OSHDINGIZ!",
            "ru": "💀 ВЫ ПРЕВЫСИЛИ ЛИМИТ!",
            "en": "💀 LIMIT EXCEEDED!"
        }

        response = response.replace(
            status_text,
            over_text.get(lang, over_text["uz"])
        )

    await msg.answer(response)
# --- Xarajat tugmasi bosilganda ko'rsatma berish ---
@router.message(F.text.in_(["➕ Xarajat", "➕ Расход", "➕ Expense"]))
async def expense_instruction(msg: Message):
    user = await get_user_data(msg.from_user.id)
    if not user:
        return await msg.answer("❗ Iltimos /start buyrug'ini yuboring")
    await msg.answer(t("expense_ask", user[1]), parse_mode="HTML")

# ================= 4-BO‘LAK YAKUNI =================
# ================= 5-BO‘LAK: MAQSADLAR VA HISOBOTLAR =================

# --- 1. MAQSAD (GOAL) BOSHQARUV MANTIQI ---

@router.message(F.text.in_(["🎯 Maqsad", "🎯 Цель", "🎯 Goal"]))
async def goal_main_handler(msg: Message, state: FSMContext):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT name, amount, days, created_at FROM goals WHERE user_id=?", (msg.from_user.id,)) as cur:
            goal = await cur.fetchone()
            
    user = await get_user_data(msg.from_user.id)
    if not user:
        return await msg.answer("❗ Iltimos /start buyrug'ini yuboring")
    lang = user[1]

    if goal:
        # Maqsad mavjud bo'lsa, statusni hisoblaymiz
        name, total_amount, total_days, created_at = goal
        created_date = datetime.fromisoformat(created_at)
        
        passed_days = (datetime.now() - created_date).days
        left_days = max(total_days - passed_days, 0)
        
        # Progress hisobi (Vaqtga nisbatan)
        progress_percent = int((passed_days / total_days) * 100) if total_days > 0 else 0
        progress_percent = min(progress_percent, 100)
        bar = "█" * (progress_percent // 10) + "░" * (10 - (progress_percent // 10))
        
        response = (
            f"╔══════════════════╗\n"
            f"      🎯 MAQSAD\n"
            f"╚══════════════════╝\n\n"
            f"📱 {name}\n"
            f"💰 {total_amount:,}\n\n"
            f"⏳ {passed_days} kun o‘tdi\n"
            f"📉 {left_days} kun qoldi\n\n"
            f"{bar} {progress_percent}%\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Yangi maqsad qo'shasizmi?\n"
            f"Yoki bu maqsadni o'chirasizmi?"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Yangi", callback_data="goal_new"), 
                InlineKeyboardButton(text="🗑 O'chirish", callback_data="goal_delete")
            ],
            [InlineKeyboardButton(text="❌ Yo'q", callback_data="goal_cancel")]
        ])
        await msg.answer(response, reply_markup=kb)
    else:
        # Maqsad yo'q bo'lsa, yangi yaratishni boshlaymiz
        await msg.answer(t("goal_ask_name", lang))
        await state.set_state(GoalSet.title)

# --- 2. MAQSADNI QADAM-BAQADAM YARATISH ---

@router.message(GoalSet.title)
async def goal_name_set(msg: Message, state: FSMContext):
    user = await get_user_data(msg.from_user.id)
    if not user:
        return await msg.answer("❗ Iltimos /start buyrug'ini yuboring")
    lang = user[1]
    await state.update_data(title=msg.text.strip(), lang=lang)
    await msg.answer(t("goal_ask_money", lang))
    await state.set_state(GoalSet.money)

@router.message(GoalSet.money)
async def goal_money_set(msg: Message, state: FSMContext):
    raw_text = re.sub(r"\D", "", msg.text or "")
    if not raw_text:
        return await msg.answer("❌ Faqat raqam yozing! Masalan: 100000")
    amount = int(raw_text)
    if amount <= 0:
        return await msg.answer("❌ Summani 0 dan katta qilib kiriting.")
    data = await state.get_data()
    lang = data.get("lang", "uz")
    await state.update_data(money=amount)
    await msg.answer(t("goal_ask_days", lang))
    await state.set_state(GoalSet.days)

@router.message(GoalSet.days)
async def goal_days_finish(msg: Message, state: FSMContext):
    raw_text = re.sub(r"\D", "", msg.text or "")
    if not raw_text:
        return await msg.answer("❌ Faqat raqam yozing! Masalan: 30")
    days = int(raw_text)
    if days <= 0:
        return await msg.answer("❌ Kunlar soni 0 dan katta bo'lishi kerak.")
    
    data = await state.get_data()
    if not data or 'title' not in data or 'money' not in data:
        return await msg.answer("❌ Xatolik yuz berdi. Qayta boshlang.")
    
    lang = data.get("lang", "uz")
    title = data['title']
    amount = data['money']
    
    per_day = amount // days if days > 0 else amount
    created_at = datetime.now().isoformat()
    
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR REPLACE INTO goals (user_id, name, amount, days, created_at) VALUES (?, ?, ?, ?, ?)",
                         (msg.from_user.id, title, amount, days, created_at))
        await db.commit()
    
    response = (
        f"╔══════════════════╗\n"
        f"   🎯 YANGI MAQSAD\n"
        f"╚══════════════════╝\n\n"
        f"📱 {title}\n"
        f"💰 {amount:,}\n"
        f"📅 {days} kun\n\n"
        f"💸 Kuniga: {per_day:,}\n\n"
        f"🚀 Boshladik!\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    await msg.answer(response, reply_markup=main_menu_kb(lang))
    await state.clear()

# --- GOAL CALLBACK HANDLERS ---
@router.callback_query(F.data == "goal_new")
async def goal_new_callback(call: CallbackQuery, state: FSMContext):
    user = await get_user_data(call.from_user.id)
    if not user:
        return await call.answer("❗ Iltimos /start buyrug'ini yuboring")
    lang = user[1]
    
    await call.message.answer(t("goal_ask_name", lang))
    await state.set_state(GoalSet.title)
    await call.answer()

@router.callback_query(F.data == "goal_delete")
async def goal_delete_callback(call: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM goals WHERE user_id=?", (call.from_user.id,))
        await db.commit()
    
    user = await get_user_data(call.from_user.id)
    lang = user[1] if user else "uz"
    
    await call.answer()
    await call.message.answer("✅ Maqsad o'chirildi", reply_markup=main_menu_kb(lang))

@router.callback_query(F.data == "goal_cancel")
async def goal_cancel_callback(call: CallbackQuery):
    user = await get_user_data(call.from_user.id)
    lang = user[1] if user else "uz"
    
    await call.answer()
    await call.message.delete()

# --- 3. HISOBOT (ANALIZ) MANTIQI ---

@router.message(F.text.in_(["📊 Hisobot", "📊 Отчет", "📊 Report"]))
async def show_weekly_report(msg: Message):
    user = await get_user_data(msg.from_user.id)
    if not user:
        return await msg.answer("❗ Iltimos /start buyrug'ini yuboring")
    lang = user[1]
    
    async with aiosqlite.connect(DB) as db:
        # Oxirgi 7 kundagi xarajatlarni kategoriyalar bo'yicha yig'amiz
        query = """
            SELECT category, SUM(amount) FROM expenses 
            WHERE user_id = ? AND created_at >= date('now', '-7 days')
            GROUP BY category
        """
        async with db.execute(query, (msg.from_user.id,)) as cur:
            rows = await cur.fetchall()
            
        # Jami sarf va eng faol kunni aniqlash
        async with db.execute("SELECT SUM(amount) FROM expenses WHERE user_id=? AND created_at >= date('now', '-7 days')", (msg.from_user.id,)) as cur:
            total_sum = (await cur.fetchone())[0] or 0
            
        async with db.execute("SELECT date(created_at), SUM(amount) FROM expenses WHERE user_id=? GROUP BY date(created_at) ORDER BY SUM(amount) DESC LIMIT 1", (msg.from_user.id,)) as cur:
            top_day_row = await cur.fetchone()

    if not rows:
        return await msg.answer(t("no_expenses_7days", lang))

    # Hisobot matnini yig'ish
    report = t("report_title", lang)
    icons = {"Ovqat": "🍔", "Transport": "🚕", "Xarid": "🛒", "Boshqa": "📦"}
    
    for cat, amount in rows:
        translated_cat = translate_category(cat, lang)
        percent = int((amount / total_sum) * 100) if total_sum > 0 else 0
        report += f"{icons.get(cat, '📦')} {translated_cat}: {amount:,} ({percent}%)\n"
        
    report += t("report_total", lang, total=total_sum)
    report += t("report_average", lang, avg=total_sum // 7 if total_sum > 0 else 0)
    
    if top_day_row:
        report += t("report_top_day", lang, amount=top_day_row[1], date=top_day_row[0])
        
    # SMM maslahati
    biggest_cat = max(rows, key=lambda x: x[1])[0]
    translated_biggest = translate_category(biggest_cat, lang)
    report += f"\n\n{t('advice_high_expense', lang, category=translated_biggest)}"
    
    await msg.answer(report, parse_mode="HTML")

# ================= 5-BO‘LAK YAKUNI =================
# ================= 6-BO‘LAK: TARIX VA AVTO-ESLATMALAR =================

# --- 1. TARIX BULIMI (HISTORY) ---

@router.message(F.text.contains("Tarix") | F.text.contains("История") | F.text.contains("History"))
async def history_main(msg: Message):
    user = await get_user_data(msg.from_user.id)
    if not user:
        return await msg.answer("❗ Iltimos /start buyrug'ini yuboring")
    lang = user[1]
    
    # Shaffof tugmalar: Kechagi kun, 7 kun, 30 kun
    btns = t("btn_history", lang)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"1️⃣ {btns[0]}", callback_data="hist_1")],
        [InlineKeyboardButton(text=f"2️⃣ {btns[1]}", callback_data="hist_7")],
        [InlineKeyboardButton(text=f"3️⃣ {btns[2]}", callback_data="hist_30")]
    ])
    
    await msg.answer(t("history_period", lang), reply_markup=kb)

@router.callback_query(F.data.in_(["hist_1", "hist_7", "hist_30"]))
async def show_history_data(call: CallbackQuery):
    days = int(call.data.split("_")[1])
    uid = call.from_user.id
    
    user = await get_user_data(uid)
    if not user:
        return await call.message.answer("❗ Iltimos /start buyrug'ini yuboring")
    lang = user[1]
    
    # SQL so'rovi: Tanlangan davr bo'yicha xarajatlarni olish
    async with aiosqlite.connect(DB) as db:
        if days == 1: # Kechagi kun
            query = "SELECT amount, category, time(created_at) FROM expenses WHERE user_id=? AND date(created_at) = date('now', '-1 day')"
            params = (uid,)
        else: # 7 yoki 30 kun
            query = "SELECT amount, category, date(created_at) FROM expenses WHERE user_id=? AND created_at >= date('now', ?)"
            params = (uid, f"-{days} days")
            
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()

    if not rows:
        await call.answer(t("history_no_data", lang), show_alert=True)
        return

    res_text = t("history_title", lang, days=days)
    for r in rows:
        translated_cat = translate_category(r[1], lang)
        res_text += t("history_item", lang, amount=r[0], category=translated_cat, time=r[2])
    
    # Xabar uzun bo'lsa bo'lib yuborish
    if len(res_text) > 4096:
        res_text = res_text[:4090] + "..."
        
    await call.answer()
    await call.message.answer(res_text, parse_mode="HTML")

# --- 2. AVTOMATIK ESLATMALAR (SCHEDULER) ---

async def auto_reminder_task():
    """Har kuni 06:00 va 23:00 da ishlaydigan tizim"""
    while True:
        try:
            uz_tz = pytz.timezone("Asia/Tashkent")
            now = datetime.now(uz_tz)
            
            # Barcha foydalanuvchilarni olish
            async with aiosqlite.connect(DB) as db:
                async with db.execute("SELECT user_id, name, lang, limit_amount FROM users") as cur:
                    all_users = await cur.fetchall()

            # ERTALABKI ESLATMA (06:00)
            if now.hour == 6 and now.minute == 0:
                for user in all_users:
                    uid, name, lang, limit = user
                    try:
                        morning_msg = (
                            f"🌅 <b>XAYRLI TONG {name.upper()}!</b>\n\n"
                            f"💰 Bugungi limit: {limit:,}\n\n"
                            f"⚙️ Limit qo'yishni unutmang"
                        )
                        await bot.send_message(uid, morning_msg, parse_mode="HTML")
                    except: continue # Botni bloklagan bo'lsa o'tib ketadi
                await asyncio.sleep(60)

            # KECHKI HISOBOT (23:00)
            if now.hour == 23 and now.minute == 0:
                for user in all_users:
                    uid, name, lang, limit = user
                    try:
                        # Bugungi sarfni hisoblash
                        async with aiosqlite.connect(DB) as db:
                            async with db.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? AND date(created_at)=date('now') GROUP BY category", (uid,)) as cur:
                                daily_rows = await cur.fetchall()
                            async with db.execute("SELECT SUM(amount) FROM expenses WHERE user_id=? AND date(created_at)=date('now')", (uid,)) as cur:
                                total_day = (await cur.fetchone())[0] or 0

                        if total_day > 0:
                            status, p_bar, percent = get_visual_report(total_day, limit)
                            
                            report = f"🌙 <b>KUN YAKUNI</b>\n\n"
                            report += f"💰 Limit: {limit:,}\n"
                            report += f"💸 Sarflandi: {total_day:,}\n\n"
                            
                            for cat, amt in daily_rows:
                                report += f"• {cat}: {amt:,}\n"
                            
                            report += f"\n📉 Qolgan: {max(limit - total_day, 0):,}\n\n"
                            report += f"{p_bar}\n\n"
                            report += "🔥 Zo'r!" if percent <= 100 else "⚠️ Tejamkor bo'ling!"
                            
                            await bot.send_message(uid, report, parse_mode="HTML")
                    except: continue
                await asyncio.sleep(60)

        except Exception as e:
            print(f"Scheduler Error: {e}")
        
        await asyncio.sleep(30) # Har 30 soniyada vaqtni tekshiradi

# ================= 6-BO‘LAK YAKUNI =================
# ================= 7-BO‘LAK: ADMIN PANEL VA MAIN RUNNER =================

# --- 1. JONLI STATISTIKANI YANGILASH ---
async def update_bot_status():
    """Bot profilidagi foydalanuvchilar sonini yangilash"""
    try:
        async with aiosqlite.connect(DB) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cur:
                count = (await cur.fetchone())[0]
        
        # Bot nomining ostidagi qisqacha tavsifni yangilash
        # Eslatma: Bu funksiya botning "About" qismida sonni ko'rsatadi
        await bot.set_my_short_description(f"💰 Tejamkor Bot | {count:,} foydalanuvchi")
    except Exception as e:
        print(f"Status Update Error: {e}")

# --- 2. ADMIN PANEL KOMANDALARI ---
@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_main(msg: Message):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]
    
    admin_text = (
        f"👨‍💻 <b>ADMIN PANEL</b>\n\n"
        f"📊 Jami foydalanuvchilar: {total_users:,} ta\n"
        f"🌐 Holat: Faol\n\n"
        f"📢 Reklama yuborish uchun xabar matnini <code>/send</code> komandasi bilan yozing.\n"
        f"Masalan: <code>/send Salom hammaga!</code>"
    )
    await msg.answer(admin_text, parse_mode="HTML")

@router.message(Command("send"), F.from_user.id == ADMIN_ID)
async def admin_broadcast(msg: Message):
    # Xabardan komandani olib tashlash
    broadcast_text = msg.text.replace("/send", "").strip()
    
    if not broadcast_text:
        return await msg.answer("❌ Reklama matni bo'sh bo'lishi mumkin emas!")

    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()

    send_count = 0
    error_count = 0
    
    status_msg = await msg.answer(f"⏳ Reklama yuborilmoqda: 0/{len(users)}")

    for user in users:
        try:
            await bot.send_message(user[0], broadcast_text)
            send_count += 1
            # Telegram bloklamasligi uchun kichik pauza
            if send_count % 20 == 0:
                await asyncio.sleep(0.5)
        except Exception:
            error_count += 1
            continue
            
    await status_msg.edit_text(
        f"📢 <b>Reklama yakunlandi!</b>\n\n"
        f"✅ Yuborildi: {send_count}\n"
        f"❌ Xatolik (Blok): {error_count}", 
        parse_mode="HTML"
    )

# --- 3. BOTNI ISHGA TUSHIRISH (MAIN RUNNER) ---
async def main():
    # 1. Ma'lumotlar bazasini tekshirish va yaratish
    await init_db()
    
    # 2. Avto-eslatmalar va Statistika yangilashni alohida task qilib ishga tushirish
    asyncio.create_task(auto_reminder_task())
    asyncio.create_task(daily_limit_reset())
    
    # 3. Har 1 soatda foydalanuvchilar sonini yangilab turish
    async def status_loop():
        while True:
            await update_bot_status()
            await asyncio.sleep(3600) # 1 soat
    asyncio.create_task(status_loop())

    # 4. Bot komandalarini menyuda ko'rsatish
    commands = [
        BotCommand(command="start", description="Botni qayta ishga tushirish"),
        BotCommand(command="admin", description="Admin panel (faqat admin uchun)")
    ]
    await bot.set_my_commands(commands)

    # 5. Pollingni boshlash
    print("---")
    print("🚀 TEJAMKOR BOT MUVAFFAQIYATLI ISHGA TUSHDI!")
    print(f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("---")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    # Loggingni yoqish (xatolarni ko'rish uchun)
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Bot to'xtatildi.")
