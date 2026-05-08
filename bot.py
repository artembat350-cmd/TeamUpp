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

# ========================
# БАЗА ДАННЫХ
# ========================

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
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            message_id INTEGER
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

def save_project(user_id, title, message_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("INSERT INTO projects (user_id, title, message_id) VALUES (?, ?, ?)", (user_id, title, message_id))
    conn.commit()
    conn.close()

def get_user_projects(user_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT title, message_id FROM projects WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

# ========================
# СОСТОЯНИЯ
# ========================

REG_NAME, REG_ROLE, REG_CONTACT = range(3)

EDIT_FIELD, EDIT_VALUE = range(20, 22)

(
    PROJ_NAME,
    PROJ_DESC,
    PROJ_LINK,
    PROJ_STAGE,
    PROJ_ROLE_NAME,
    PROJ_ROLE_SPEC,
    PROJ_ROLE_SKILLS,
    PROJ_ROLE_EXP,
    PROJ_ROLE_HOURS,
    PROJ_ROLE_LOCATION,
    PROJ_ROLE_PAYMENT,
    PROJ_ROLE_MORE,
    PROJ_EXTRA_CONTACT,
    PROJ_EXTRA_CONTACT_VALUE,
    PROJ_CONFIRM,
) = range(30, 45)

# ========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ========================

def build_roles_text(roles):
    text = ""
    for i, role in enumerate(roles, 1):
        text += (
            f"\n👤 *Роль {i}: {role['name']}*\n"
            f"   🎯 Специализация: {role['spec']}\n"
            f"   🛠 Навыки: {role['skills']}\n"
            f"   📋 Опыт: {role['exp']}\n"
            f"   ⏰ Занятость: {role['hours']}\n"
            f"   📍 Местоположение: {role['location']}\n"
            f"   💵 Оплата: {role['payment']}\n"
        )
    return text

def build_post(data, author_name, author_role, author_contact):
    roles_text = build_roles_text(data["roles"])
    link_line = f"🌐 *Ссылка:* {data['proj_link']}\n" if data.get("proj_link") else ""
    contact_line = data.get("extra_contact") or author_contact

    return (
        f"🚀 *{data['proj_name']}*\n\n"
        f"💡 *Описание:* {data['proj_desc']}\n\n"
        f"📍 *Этап проекта:* {data['proj_stage']}\n"
        f"{link_line}"
        f"\n━━━━━━━━━━━━━━━\n"
        f"🔍 *Ищем в команду:*\n"
        f"{roles_text}"
        f"━━━━━━━━━━━━━━━\n\n"
        f"👤 *Автор:* {author_name} — {author_role}\n"
        f"📩 *Написать:* {contact_line}"
    )

# ========================
# РЕГИСТРАЦИЯ
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if get_user(user_id):
        await update.message.reply_text(
            "Ты уже зарегистрирован! ✅\n\n"
            "Доступные команды:\n"
            "/newproject — создать пост о проекте\n"
            "/myprojects — мои проекты\n"
            "/editprofile — изменить профиль"
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "👋 Привет! Это бот для поиска команды.\n\nДавай зарегистрируемся. Как тебя зовут?"
    )
    return REG_NAME

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    roles = [["Руководитель проекта", "Участник проекта"]]
    await update.message.reply_text(
        "Какая твоя роль?",
        reply_markup=ReplyKeyboardMarkup(roles, one_time_keyboard=True, resize_keyboard=True)
    )
    return REG_ROLE

async def reg_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["role"] = update.message.text
    await update.message.reply_text(
        "Как с тобой связаться?\n(напиши свой Telegram username, например @username)",
        reply_markup=ReplyKeyboardRemove()
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
        f"Используй /newproject чтобы создать пост о проекте."
    )
    return ConversationHandler.END

# ========================
# РЕДАКТИРОВАНИЕ ПРОФИЛЯ
# ========================

async def edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return ConversationHandler.END

    fields = [["Имя", "Роль"], ["Контакт"]]
    await update.message.reply_text(
        f"Текущий профиль:\n"
        f"👤 Имя: {user[1]}\n"
        f"🎭 Роль: {user[2]}\n"
        f"📩 Контакт: {user[3]}\n\n"
        f"Что хочешь изменить?",
        reply_markup=ReplyKeyboardMarkup(fields, one_time_keyboard=True, resize_keyboard=True)
    )
    return EDIT_FIELD

async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_field"] = update.message.text
    await update.message.reply_text(
        f"Введи новое значение для «{update.message.text}»:",
        reply_markup=ReplyKeyboardRemove()
    )
    return EDIT_VALUE

async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    field = context.user_data["edit_field"]
    new_value = update.message.text

    name = user[1]
    role = user[2]
    contact = user[3]

    if field == "Имя":
        name = new_value
    elif field == "Роль":
        role = new_value
    elif field == "Контакт":
        contact = new_value

    save_user(user_id, name, role, contact)
    await update.message.reply_text(f"✅ «{field}» обновлено!")
    return ConversationHandler.END

# ========================
# МОИ ПРОЕКТЫ
# ========================

async def my_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not get_user(user_id):
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return

    projects = get_user_projects(user_id)
    if not projects:
        await update.message.reply_text("У тебя пока нет опубликованных проектов.\n\nСоздай первый: /newproject")
        return

    text = "📋 *Твои проекты:*\n\n"
    for i, (title, message_id) in enumerate(projects, 1):
        if message_id:
            text += f"{i}. [{title}](https://t.me/c/{str(GROUP_ID)[4:]}/{message_id})\n"
        else:
            text += f"{i}. {title}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ========================
# СОЗДАНИЕ ПРОЕКТА
# ========================

async def new_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not get_user(user_id):
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return ConversationHandler.END
    context.user_data["roles"] = []
    context.user_data["extra_contact"] = None
    context.user_data["proj_link"] = None
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
        "🌐 Есть ли ссылка на проект, лендинг или прототип?\n"
        "(вставь ссылку или напиши «Нет»)"
    )
    return PROJ_LINK

async def proj_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["proj_link"] = None if text.lower() in ["нет", "no", "-"] else text
    await update.message.reply_text(
        "📍 На каком этапе находится проект?\n(например: идея, есть MVP, работающий продукт)"
    )
    return PROJ_STAGE

async def proj_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_stage"] = update.message.text
    await update.message.reply_text(
        "👥 Отлично! Теперь добавим роли в команду.\n\n"
        "Как называется первая роль?\n(например: Backend-разработчик, UI/UX дизайнер, Маркетолог)"
    )
    return PROJ_ROLE_NAME

async def proj_role_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"] = {"name": update.message.text}
    await update.message.reply_text(
        "🎯 Направление / специализация для этой роли?\n"
        "(например: мобильная разработка iOS, веб-дизайн, SMM)"
    )
    return PROJ_ROLE_SPEC

async def proj_role_spec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["spec"] = update.message.text
    await update.message.reply_text(
        "🛠 Ключевые навыки и технологии?\n"
        "(например: Python, FastAPI, PostgreSQL / Figma, Adobe XD)"
    )
    return PROJ_ROLE_SKILLS

async def proj_role_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["skills"] = update.message.text
    await update.message.reply_text(
        "📋 Какой опыт работы требуется для этой роли?\n"
        "(например: от 1 года в коммерческой разработке, опыт с React / или напиши «Не требуется»)"
    )
    return PROJ_ROLE_EXP

async def proj_role_exp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["exp"] = update.message.text
    hours = [["Полная занятость", "Частичная занятость"], ["Пару часов в неделю", "Обсуждаемо"]]
    await update.message.reply_text(
        "⏰ Какая занятость нужна для этой роли?",
        reply_markup=ReplyKeyboardMarkup(hours, one_time_keyboard=True, resize_keyboard=True)
    )
    return PROJ_ROLE_HOURS

async def proj_role_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["hours"] = update.message.text
    await update.message.reply_text(
        "📍 Место проживания для этой роли?\n(напиши город, страну или «Любое»)",
        reply_markup=ReplyKeyboardRemove()
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
        yesno = [["✅ Да, добавить другой контакт", "➡️ Нет, использовать контакт из профиля"]]
        await update.message.reply_text(
            "📞 Хочешь указать отдельный контакт для связи по этому проекту?",
            reply_markup=ReplyKeyboardMarkup(yesno, one_time_keyboard=True, resize_keyboard=True)
        )
        return PROJ_EXTRA_CONTACT

async def proj_extra_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Да, добавить другой контакт":
        await update.message.reply_text(
            "Напиши контакт для связи по этому проекту:\n(например: @username, email или номер телефона)",
            reply_markup=ReplyKeyboardRemove()
        )
        return PROJ_EXTRA_CONTACT_VALUE
    else:
        return await show_preview(update, context)

async def proj_extra_contact_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["extra_contact"] = update.message.text
    return await show_preview(update, context)

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    author_name, author_role, author_contact = user[1], user[2], user[3]
    post_text = build_post(context.user_data, author_name, author_role, author_contact)
    confirm = [["✅ Опубликовать", "❌ Отменить"]]
    await update.message.reply_text(
        f"📋 *Превью поста:*\n\n{post_text}",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(confirm, one_time_keyboard=True, resize_keyboard=True)
    )
    return PROJ_CONFIRM

async def proj_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Опубликовать":
        user_id = update.effective_user.id
        user = get_user(user_id)
        author_name, author_role, author_contact = user[1], user[2], user[3]
        post_text = build_post(context.user_data, author_name, author_role, author_contact)

        sent = await context.bot.send_message(chat_id=GROUP_ID, text=post_text, parse_mode="Markdown")
        save_project(user_id, context.user_data["proj_name"], sent.message_id)

        await update.message.reply_text("✅ Пост опубликован в группу!", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("❌ Публикация отменена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ========================
# ОТМЕНА
# ========================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ========================
# ЗАПУСК
# ========================

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

    edit_handler = ConversationHandler(
        entry_points=[CommandHandler("editprofile", edit_profile)],
        states={
            EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field)],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    proj_handler = ConversationHandler(
        entry_points=[CommandHandler("newproject", new_project)],
        states={
            PROJ_NAME:               [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_name)],
            PROJ_DESC:               [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_desc)],
            PROJ_LINK:               [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_link)],
            PROJ_STAGE:              [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_stage)],
            PROJ_ROLE_NAME:          [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_name)],
            PROJ_ROLE_SPEC:          [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_spec)],
            PROJ_ROLE_SKILLS:        [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_skills)],
            PROJ_ROLE_EXP:           [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_exp)],
            PROJ_ROLE_HOURS:         [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_hours)],
            PROJ_ROLE_LOCATION:      [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_location)],
            PROJ_ROLE_PAYMENT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_payment)],
            PROJ_ROLE_MORE:          [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_more)],
            PROJ_EXTRA_CONTACT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_extra_contact)],
            PROJ_EXTRA_CONTACT_VALUE:[MessageHandler(filters.TEXT & ~filters.COMMAND, proj_extra_contact_value)],
            PROJ_CONFIRM:            [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_handler)
    app.add_handler(edit_handler)
    app.add_handler(proj_handler)
    app.add_handler(CommandHandler("myprojects", my_projects))

    logger.info("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
