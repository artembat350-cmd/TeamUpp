import logging
import sqlite3
import json
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = "8644250144:AAFaWko2PTltYWKKDJ_G_P6TdrmyLg-Axkc"
GROUP_ID = -1003934966038

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RULES_TEXT = (
    "📋 *Правила публикации проекта*\n\n"
    "*Запрещено:*\n"
    "• Дублировать один и тот же проект несколько раз\n"
    "• Публиковать проекты с целью сбора личных данных\n"
    "• Рекламировать сторонние сервисы, курсы, продукты\n"
    "• Использовать бота для спама или массовой рассылки\n"
    "• Публиковать проекты без реального намерения набирать команду\n"
    "• Повторная публикация одного проекта — не чаще раза в день\n\n"
    "Нарушение правил ведёт к удалению поста.\n\n"
    "Принимаешь правила?"
)

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
            contact TEXT,
            rules_accepted INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            message_id INTEGER,
            status TEXT DEFAULT 'active',
            last_published TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS project_data (
            project_id INTEGER PRIMARY KEY,
            data TEXT
        )
    """)
    for col in ["rules_accepted INTEGER DEFAULT 0"]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except:
            pass
    for col in ["status TEXT DEFAULT 'active'", "last_published TEXT"]:
        try:
            c.execute(f"ALTER TABLE projects ADD COLUMN {col}")
        except:
            pass
    conn.commit()
    conn.close()

def save_user(user_id, name, role, contact):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO users (user_id, name, role, contact, rules_accepted) VALUES (?, ?, ?, ?, COALESCE((SELECT rules_accepted FROM users WHERE user_id=?), 0))",
        (user_id, name, role, contact, user_id)
    )
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def set_rules_accepted(user_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET rules_accepted = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def has_accepted_rules(user_id):
    user = get_user(user_id)
    return bool(user and len(user) > 4 and user[4] == 1)

def save_project(user_id, title, message_id, data_json):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO projects (user_id, title, message_id, status, last_published) VALUES (?, ?, ?, 'active', ?)",
        (user_id, title, message_id, now)
    )
    project_id = c.lastrowid
    c.execute("INSERT INTO project_data (project_id, data) VALUES (?, ?)", (project_id, data_json))
    conn.commit()
    conn.close()
    return project_id

def get_user_projects(user_id, status='active'):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT id, title, message_id, last_published FROM projects WHERE user_id = ? AND status = ?", (user_id, status))
    rows = c.fetchall()
    conn.close()
    return rows

def get_active_project_count(user_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM projects WHERE user_id = ? AND status = 'active'", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_project_data(project_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT data FROM project_data WHERE project_id = ?", (project_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def update_project_data(project_id, data_json):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE project_data SET data = ? WHERE project_id = ?", (data_json, project_id))
    conn.commit()
    conn.close()

def update_project_title(project_id, title):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE projects SET title = ? WHERE id = ?", (title, project_id))
    conn.commit()
    conn.close()

def close_project(project_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE projects SET status = 'closed' WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

def update_project_published(project_id, message_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE projects SET last_published = ?, message_id = ? WHERE id = ?", (now, message_id, project_id))
    conn.commit()
    conn.close()

def can_republish(project_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT last_published FROM projects WHERE id = ?", (project_id,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        return True
    return datetime.now() - datetime.fromisoformat(row[0]) >= timedelta(days=1)

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
    PROJ_ROLE_DESC,
    PROJ_ROLE_EXP,
    PROJ_ROLE_HOURS,
    PROJ_ROLE_LOCATION,
    PROJ_ROLE_PAYMENT,
    PROJ_ROLE_MORE,
    PROJ_EXTRA_CONTACT,
    PROJ_EXTRA_CONTACT_VALUE,
    PROJ_RULES,
    PROJ_CONFIRM,
) = range(30, 46)

(
    MY_SELECT_PROJECT,
    MY_PROJECT_ACTION,
    MY_EDIT_FIELD,
    MY_EDIT_VALUE,
    MY_CONFIRM_DELETE,
    MY_SELECT_ROLE,
    MY_EDIT_ROLE_FIELD,
    MY_EDIT_ROLE_VALUE,
) = range(60, 68)

# ========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ========================

def build_roles_text(roles):
    text = ""
    for i, role in enumerate(roles, 1):
        text += (
            f"\n👤 *Роль {i}: {role['name']}*\n"
            f"   🎯 Специализация: {role['spec']}\n"
            f"   📝 Описание роли: {role['desc']}\n"
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
            "📋 *Доступные команды:*\n\n"
            "/newproject — создать пост о проекте\n"
            "/myprojects — мои проекты\n"
            "/editprofile — изменить профиль\n"
            "/cancel — отменить текущее действие",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    await update.message.reply_text("👋 Привет! Это бот для поиска команды.\n\nДавай зарегистрируемся. Как тебя зовут?")
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
        f"📋 *Доступные команды:*\n\n"
        f"/newproject — создать пост о проекте\n"
        f"/myprojects — мои проекты\n"
        f"/editprofile — изменить профиль\n"
        f"/cancel — отменить текущее действие",
        parse_mode="Markdown"
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
    name, role, contact = user[1], user[2], user[3]
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
        return ConversationHandler.END
    projects = get_user_projects(user_id, 'active')
    if not projects:
        await update.message.reply_text("У тебя пока нет активных проектов.\n\nСоздай первый: /newproject")
        return ConversationHandler.END
    context.user_data["my_projects"] = projects
    lines = [f"{i}. {p[1]}" for i, p in enumerate(projects, 1)]
    buttons = [[p[1]] for p in projects]
    await update.message.reply_text(
        "📋 *Твои активные проекты:*\n\n" + "\n".join(lines) + "\n\nВыбери проект:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
    )
    return MY_SELECT_PROJECT

async def my_select_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text
    projects = context.user_data.get("my_projects", [])
    selected = next((p for p in projects if p[1] == title), None)
    if not selected:
        await update.message.reply_text("Проект не найден.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    context.user_data["selected_project"] = selected
    actions = [["✏️ Редактировать проект", "👥 Редактировать роли"], ["🔄 Опубликовать снова", "🗑 Удалить из профиля"]]
    await update.message.reply_text(
        f"Проект: *{title}*\n\nЧто хочешь сделать?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(actions, one_time_keyboard=True, resize_keyboard=True)
    )
    return MY_PROJECT_ACTION

async def my_project_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = update.message.text
    project = context.user_data["selected_project"]
    project_id = project[0]

    if action == "🔄 Опубликовать снова":
        if not can_republish(project_id):
            await update.message.reply_text(
                "⏳ Повторная публикация возможна не чаще раза в день.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        raw = get_project_data(project_id)
        if not raw:
            await update.message.reply_text("Данные проекта не найдены.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        data = json.loads(raw)
        user_id = update.effective_user.id
        user = get_user(user_id)
        post_text = build_post(data, user[1], user[2], user[3])
        sent = await context.bot.send_message(chat_id=GROUP_ID, text=post_text, parse_mode="Markdown")
        update_project_published(project_id, sent.message_id)
        await update.message.reply_text("✅ Проект опубликован снова!", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    elif action == "🗑 Удалить из профиля":
        confirm = [["✅ Да, удалить", "❌ Отмена"]]
        await update.message.reply_text(
            "Удалить проект из профиля?\nПост в группе останется.",
            reply_markup=ReplyKeyboardMarkup(confirm, one_time_keyboard=True, resize_keyboard=True)
        )
        return MY_CONFIRM_DELETE

    elif action == "✏️ Редактировать проект":
        fields = [
            ["Название", "Описание проекта"],
            ["Ссылка на проект", "Этап проекта"],
            ["Контакт для связи"]
        ]
        await update.message.reply_text(
            "Что хочешь изменить в проекте?",
            reply_markup=ReplyKeyboardMarkup(fields, one_time_keyboard=True, resize_keyboard=True)
        )
        return MY_EDIT_FIELD

    elif action == "👥 Редактировать роли":
        raw = get_project_data(project_id)
        if not raw:
            await update.message.reply_text("Данные не найдены.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        data = json.loads(raw)
        roles = data.get("roles", [])
        if not roles:
            await update.message.reply_text("В проекте нет ролей.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        context.user_data["project_data"] = data
        buttons = [[f"Роль {i+1}: {r['name']}"] for i, r in enumerate(roles)]
        await update.message.reply_text(
            "Выбери роль для редактирования:",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        )
        return MY_SELECT_ROLE

    await update.message.reply_text("Неизвестное действие.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def my_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Да, удалить":
        close_project(context.user_data["selected_project"][0])
        await update.message.reply_text("✅ Проект удалён из профиля.\nПост в группе остался.", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def my_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_project_field"] = update.message.text
    await update.message.reply_text(
        f"Введи новое значение для «{update.message.text}»:",
        reply_markup=ReplyKeyboardRemove()
    )
    return MY_EDIT_VALUE

async def my_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project = context.user_data["selected_project"]
    project_id = project[0]
    field = context.user_data["edit_project_field"]
    new_value = update.message.text
    raw = get_project_data(project_id)
    if not raw:
        await update.message.reply_text("Данные не найдены.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    data = json.loads(raw)
    if field == "Название":
        data["proj_name"] = new_value
        update_project_title(project_id, new_value)
    elif field == "Описание проекта":
        data["proj_desc"] = new_value
    elif field == "Ссылка на проект":
        data["proj_link"] = None if new_value.lower() in ["нет", "no", "-"] else new_value
    elif field == "Этап проекта":
        data["proj_stage"] = new_value
    elif field == "Контакт для связи":
        data["extra_contact"] = new_value
    update_project_data(project_id, json.dumps(data, ensure_ascii=False))
    await update.message.reply_text(
        f"✅ «{field}» обновлено!\n\nИспользуй «Опубликовать снова» чтобы выложить обновлённый пост.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ========================
# РЕДАКТИРОВАНИЕ РОЛЕЙ
# ========================

async def my_select_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    data = context.user_data.get("project_data", {})
    roles = data.get("roles", [])

    role_index = None
    for i, r in enumerate(roles):
        if f"Роль {i+1}: {r['name']}" == text:
            role_index = i
            break

    if role_index is None:
        await update.message.reply_text("Роль не найдена.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    context.user_data["edit_role_index"] = role_index
    role = roles[role_index]

    fields = [
        ["Название роли", "Специализация"],
        ["Описание роли", "Опыт работы"],
        ["Занятость", "Местоположение"],
        ["Оплата"]
    ]
    await update.message.reply_text(
        f"Редактируем: *{role['name']}*\n\nЧто хочешь изменить?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(fields, one_time_keyboard=True, resize_keyboard=True)
    )
    return MY_EDIT_ROLE_FIELD

async def my_edit_role_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_role_field"] = update.message.text

    hints = {
        "Название роли": "например: Backend-разработчик, Маркетолог",
        "Специализация": "например: мобильная разработка iOS, веб-дизайн",
        "Описание роли": "чем будет заниматься человек, какие задачи решать",
        "Опыт работы": "например: от 1 года / или «Не требуется»",
        "Занятость": "Полная занятость / Частичная занятость / Пару часов в неделю / Обсуждаемо",
        "Местоположение": "город, страна или «Любое»",
        "Оплата": "Доля в проекте / Оплата / Волонтёрство / Обсуждаемо",
    }
    hint = hints.get(update.message.text, "")

    # Для занятости и оплаты показываем кнопки
    if update.message.text == "Занятость":
        buttons = [["Полная занятость", "Частичная занятость"], ["Пару часов в неделю", "Обсуждаемо"]]
        await update.message.reply_text(
            f"Выбери занятость:",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        )
    elif update.message.text == "Оплата":
        buttons = [["Доля в проекте", "Оплата"], ["Волонтёрство", "Обсуждаемо"]]
        await update.message.reply_text(
            f"Выбери формат оплаты:",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            f"Введи новое значение для «{update.message.text}»:\n_{hint}_",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
    return MY_EDIT_ROLE_VALUE

async def my_edit_role_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    project = context.user_data["selected_project"]
    project_id = project[0]
    field = context.user_data["edit_role_field"]
    new_value = update.message.text
    role_index = context.user_data["edit_role_index"]

    raw = get_project_data(project_id)
    if not raw:
        await update.message.reply_text("Данные не найдены.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    data = json.loads(raw)
    role = data["roles"][role_index]

    field_map = {
        "Название роли": "name",
        "Специализация": "spec",
        "Описание роли": "desc",
        "Опыт работы": "exp",
        "Занятость": "hours",
        "Местоположение": "location",
        "Оплата": "payment",
    }
    key = field_map.get(field)
    if key:
        role[key] = new_value
        data["roles"][role_index] = role

    update_project_data(project_id, json.dumps(data, ensure_ascii=False))
    await update.message.reply_text(
        f"✅ «{field}» для роли обновлено!\n\nИспользуй «Опубликовать снова» чтобы выложить обновлённый пост.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ========================
# СОЗДАНИЕ ПРОЕКТА
# ========================

async def new_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not get_user(user_id):
        await update.message.reply_text("Сначала зарегистрируйся: /start")
        return ConversationHandler.END
    if get_active_project_count(user_id) >= 3:
        await update.message.reply_text(
            "⚠️ У тебя уже 3 активных проекта — это максимум.\n\n"
            "Удали один в /myprojects чтобы создать новый."
        )
        return ConversationHandler.END
    context.user_data["roles"] = []
    context.user_data["extra_contact"] = None
    context.user_data["proj_link"] = None
    if not has_accepted_rules(user_id):
        await update.message.reply_text(
            RULES_TEXT,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["✅ Принимаю правила"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return PROJ_RULES
    await update.message.reply_text("🚀 Создаём пост о проекте!\n\nКак называется твой проект?")
    return PROJ_NAME

async def proj_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Принимаю правила":
        set_rules_accepted(update.effective_user.id)
        await update.message.reply_text("✅ Отлично!\n\n🚀 Создаём пост о проекте!\n\nКак называется твой проект?", reply_markup=ReplyKeyboardRemove())
        return PROJ_NAME
    await update.message.reply_text("Необходимо принять правила для публикации.")
    return PROJ_RULES

async def proj_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_name"] = update.message.text
    await update.message.reply_text("💡 Опиши идею проекта:\nЧто делаете, какую проблему решаете и для кого?")
    return PROJ_DESC

async def proj_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_desc"] = update.message.text
    await update.message.reply_text("🌐 Есть ли ссылка на проект, лендинг или прототип?\n(вставь ссылку или напиши «Нет»)")
    return PROJ_LINK

async def proj_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["proj_link"] = None if text.lower() in ["нет", "no", "-"] else text
    await update.message.reply_text("📍 На каком этапе находится проект?\n(например: идея, есть MVP, работающий продукт)")
    return PROJ_STAGE

async def proj_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_stage"] = update.message.text
    await update.message.reply_text(
        "👥 Теперь добавим роли в команду.\n\nКак называется первая роль?\n(например: Backend-разработчик, UI/UX дизайнер)"
    )
    return PROJ_ROLE_NAME

async def proj_role_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"] = {"name": update.message.text}
    await update.message.reply_text("🎯 Направление / специализация для этой роли?\n(например: мобильная разработка iOS, веб-дизайн)")
    return PROJ_ROLE_SPEC

async def proj_role_spec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["spec"] = update.message.text
    await update.message.reply_text("📝 Описание роли:\nЧем будет заниматься человек, какие задачи решать, какие навыки нужны?")
    return PROJ_ROLE_DESC

async def proj_role_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["desc"] = update.message.text
    await update.message.reply_text("📋 Какой опыт работы требуется?\n(например: от 1 года коммерческой разработки / или «Не требуется»)")
    return PROJ_ROLE_EXP

async def proj_role_exp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["exp"] = update.message.text
    hours = [["Полная занятость", "Частичная занятость"], ["Пару часов в неделю", "Обсуждаемо"]]
    await update.message.reply_text(
        "⏰ Какая занятость нужна?",
        reply_markup=ReplyKeyboardMarkup(hours, one_time_keyboard=True, resize_keyboard=True)
    )
    return PROJ_ROLE_HOURS

async def proj_role_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_role"]["hours"] = update.message.text
    await update.message.reply_text("📍 Место проживания для этой роли?\n(напиши город, страну или «Любое»)", reply_markup=ReplyKeyboardRemove())
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
        await update.message.reply_text("Как называется следующая роль?", reply_markup=ReplyKeyboardRemove())
        return PROJ_ROLE_NAME
    yesno = [["✅ Да, добавить другой контакт", "➡️ Нет, использовать контакт из профиля"]]
    await update.message.reply_text(
        "📞 Хочешь указать отдельный контакт для связи по этому проекту?",
        reply_markup=ReplyKeyboardMarkup(yesno, one_time_keyboard=True, resize_keyboard=True)
    )
    return PROJ_EXTRA_CONTACT

async def proj_extra_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Да, добавить другой контакт":
        await update.message.reply_text("Напиши контакт для связи по этому проекту:", reply_markup=ReplyKeyboardRemove())
        return PROJ_EXTRA_CONTACT_VALUE
    return await show_preview(update, context)

async def proj_extra_contact_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["extra_contact"] = update.message.text
    return await show_preview(update, context)

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    post_text = build_post(context.user_data, user[1], user[2], user[3])
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
        post_text = build_post(context.user_data, user[1], user[2], user[3])
        sent = await context.bot.send_message(chat_id=GROUP_ID, text=post_text, parse_mode="Markdown")
        data_json = json.dumps(context.user_data, ensure_ascii=False)
        save_project(user_id, context.user_data["proj_name"], sent.message_id, data_json)
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
            PROJ_RULES:              [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_rules)],
            PROJ_NAME:               [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_name)],
            PROJ_DESC:               [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_desc)],
            PROJ_LINK:               [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_link)],
            PROJ_STAGE:              [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_stage)],
            PROJ_ROLE_NAME:          [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_name)],
            PROJ_ROLE_SPEC:          [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_spec)],
            PROJ_ROLE_DESC:          [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_role_desc)],
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

    myprojects_handler = ConversationHandler(
        entry_points=[CommandHandler("myprojects", my_projects)],
        states={
            MY_SELECT_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, my_select_project)],
            MY_PROJECT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, my_project_action)],
            MY_EDIT_FIELD:     [MessageHandler(filters.TEXT & ~filters.COMMAND, my_edit_field)],
            MY_EDIT_VALUE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, my_edit_value)],
            MY_CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, my_confirm_delete)],
            MY_SELECT_ROLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, my_select_role)],
            MY_EDIT_ROLE_FIELD:[MessageHandler(filters.TEXT & ~filters.COMMAND, my_edit_role_field)],
            MY_EDIT_ROLE_VALUE:[MessageHandler(filters.TEXT & ~filters.COMMAND, my_edit_role_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_handler)
    app.add_handler(edit_handler)
    app.add_handler(proj_handler)
    app.add_handler(myprojects_handler)

    logger.info("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
