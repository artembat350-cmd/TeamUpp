import logging
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8644250144:AAFaWko2PTltYWKKDJ_G_P6TdrmyLg-Axkc"
GROUP_ID = -1003934966038

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            role TEXT,
            contact TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_user(user_id, name, role, contact):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)", (user_id, name, role, contact))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

REG_NAME, REG_ROLE, REG_CONTACT = range(3)

(
    PROJ_NAME,
    PROJ_DESC,
    PROJ_STAGE,
    PROJ_FORMAT,
    PROJ_ROLE_NAME,
    PROJ_ROLE_SPEC,
    PROJ_ROLE_SKILLS,
    PROJ_ROLE_LOCATION,
    PROJ_ROLE_PAYMENT,
    PROJ_ROLE_MORE,
    PROJ_CONFIRM,
) = range(10, 21)

def build_roles_text(roles):
    text = ""
    for i, role in enumerate(roles, 1):
        text += (
            f"\n👤 *Роль {i}: {role['name']}*\n"
            f"   🎯 Специализация: {role['spec']}\n"
            f"   🛠 Навыки: {role['skills']}\n"
            f"   📍 Местоположение: {role['location']}\n"
            f"   💵 Оплата: {role['payment']}\n"
        )
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_user(user_id):
        await update.message.reply_text(
            "Ты уже зарегистрирован! ✅\n\nИспользуй /newproject чтобы создать пост о проекте."
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "👋 Привет! Это бот для поиска команды.\n\nДавай зарегистрируемся. Как тебя зовут?"
    )
    return REG_NAME

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "Какая твоя роль в проекте?\n(например: Основатель, Разработчик, Продакт-менеджер)"
    )
    return REG_ROLE

async def reg_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["role"] = update.message.text
    await update.message.reply_text(
        "Как с тобой связаться?\n(напиши свой Telegram username, например @username)"
    )
    return REG_CONTACT

async def reg_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = context.user_data["name"]
    role = context.user_data["role"]
    contact = update.message.text
    save_user(user_id, name, role, contact)
    await update.message.reply_text(
        f"✅ Готово, {name}! Ты зарегистрирован.\n\n"
        f"Используй /newproject чтобы создать пост о своём проекте."
    )
    return ConversationHandler.END

async def new_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not get_user(user_id):
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return ConversationHandler.END
    context.user_data["roles"] = []
    await update.message.reply_text("🚀 Создаём пост о проекте!\n\nКак называется твой проект?")
    return PROJ_NAME

async def proj_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_name"] = update.message.text
    await update.message.reply_text(
        "💡 Опиши идею проекта:\nЧто делаете, какую проблему решаете и для кого?"
    )
    return PROJ_DESC

async def proj_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_desc"] = update.message.text
    await update.message.reply_text(
        "📍 На каком этапе находится проект?\n(например: идея, есть MVP, работающий продукт)"
    )
    return PROJ_STAGE

async def proj_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_stage"] = update.message.text
    formats = [["Доля в проекте", "Оплата"], ["Волонтёрство", "Обсуждаемо"]]
    await update.message.reply_text(
        "💰 Общий формат сотрудничества в проекте?",
        reply_markup=ReplyKeyboardMarkup(formats, one_time_keyboard=True, resize_keyboard=True)
    )
    return PROJ_FORMAT

async def proj_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_format"] = update.message.text
    await update.message.reply_text(
        "👥 Отлично! Теперь добавим роли в команду.\n\n"
        "Как называется первая роль?\n(например: Backend-разработчик, UI/UX дизайнер, Маркетолог)",
        reply_markup=ReplyKeyboardRemove()
    )
    return PROJ_ROLE_NAME

async def proj_role_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"] = {"name": update.message.text}
    await update.message.reply_text(
        "🎯 Направление / специализация для этой роли?\n"
        "(например: мобильная разработка iOS, веб-дизайн, SMM и таргетированная реклама)"
    )
    return PROJ_ROLE_SPEC

async def proj_role_spec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["spec"] = update.message.text
    await update.message.reply_text(
        "🛠 Ключевые навыки и технологии?\n"
        "(например: Python, FastAPI, PostgreSQL / Figma, Adobe XD / Google Ads, Facebook Ads)"
    )
    return PROJ_ROLE_SKILLS

async def proj_role_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["skills"] = update.message.text
    await update.message.reply_text(
        "📍 Место проживания для этой роли?\n(напиши город, страну или просто «Любое»)"
    )
    return PROJ_ROLE_LOCATION

async def proj_role_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["location"] = update.message.text
    payments = [["Доля в проекте", "Оплата"], ["Волонтёрство", "Обсуждаемо"]]
    await update.message.reply_text(
        "💵 Формат оплаты для этой роли?",
        reply_markup=ReplyKeyboardMarkup(payments, one_time_keyboard=True, resize_keyboard=True)
    )
    return PROJ_ROLE_PAYMENT

async def proj_role_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["payment"] = update.message.text
    context.user_data["roles"].append(context.user_data["current_role"])
    roles_count = len(context.user_data["roles"])
    more = [["➕ Добавить ещё роль", "✅ Перейти к публикации"]]
    await update.message.reply_text(
        f"✅ Роль #{roles_count} добавлена!\n\nДобавить ещё одну роль?",
        reply_markup=ReplyKeyboardMarkup(more, one_time_keyboard=True, resize_keyboard=True)
    )
    return PROJ_ROLE_MORE

async def proj_role_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "➕ Добавить ещё роль":
        await update.message.reply_text(
            "Как называется следующая роль?\n(например: Frontend-разработчик, Копирайтер)",
            reply_markup=ReplyKeyboardRemove()
        )
        return PROJ_ROLE_NAME
    else:
        user_id = update.effective_user.id
        user = get_user(user_id)
        author_name = user[1]
        author_role = user[2]
        author_contact = user[3]
        roles_text = build_roles_text(context.user_data["roles"])
        preview = (
            f"📋 *Превью поста:*\n\n"
            f"🚀 *{context.user_data['proj_name']}*\n\n"
            f"💡 *Описание:* {context.user_data['proj_desc']}\n\n"
            f"📍 *Этап:* {context.user_data['proj_stage']}\n"
            f"💰 *Формат:* {context.user_data['proj_format']}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔍 *Ищем в команду:*\n"
            f"{roles_text}"
            f"━━━━━━━━━━━━━━━\n\n"
            f"👤 *Автор:* {author_name} — {author_role}\n"
            f"📩 *Написать:* {author_contact}"
        )
        confirm = [["✅ Опубликовать", "❌ Отменить"]]
        await update.message.reply_text(
            preview,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(confirm, one_time_keyboard=True, resize_keyboard=True)
        )
        return PROJ_CONFIRM

async def proj_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Опубликовать":
        user_id = update.effective_user.id
        user = get_user(user_id)
        author_name = user[1]
        author_role = user[2]
        author_contact = user[3]
        roles_text = build_roles_text(context.user_data["roles"])
        post = (
            f"🚀 *{context.user_data['proj_name']}*\n\n"
            f"💡 *Описание:* {context.user_data['proj_desc']}\n\n"
            f"📍 *Этап проекта:* {context.user_data['proj_stage']}\n"
            f"💰 *Формат:* {context.user_data['proj_format']}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔍 *Ищем в команду:*\n"
            f"{roles_text}"
            f"━━━━━━━━━━━━━━━\n\n"
            f"👤 *Автор:* {author_name} — {author_role}\n"
            f"📩 *Написать:* {author_contact}"
        )
        await context.bot.send_message(chat_id=GROUP_ID, text=post, parse_mode="Markdown")
        await update.message.reply_text("✅ Пост опубликован в группу!", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("❌ Публикация отменена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    reg_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REG_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_ROLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_role)],
            REG_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_contact)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    proj_handler = ConversationHandler(
        entry_points=[CommandHandler("newproject", new_project)],
        states={
            PROJ_NAME:          [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_name)],
            PROJ_DESC:          [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_desc)],
            PROJ_STAGE:         [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_stage)],
            PROJ_FORMAT:        [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_format)],
            PROJ_ROLE_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_name)],
            PROJ_ROLE_SPEC:     [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_spec)],
            PROJ_ROLE_SKILLS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_skills)],
            PROJ_ROLE_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_location)],
            PROJ_ROLE_PAYMENT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_payment)],
            PROJ_ROLE_MORE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_more)],
            PROJ_CONFIRM:       [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_handler)
    app.add_handler(proj_handler)

    logger.info("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
