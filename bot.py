import logging
import json
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

# ====== НАСТРОЙКИ ======
BOT_TOKEN = "8644250144:AAFaWko2PTltYWKKDJ_G_P6TdrmyLg-Axkc"
GROUP_ID = -5280148754
# =======================

logging.basicConfig(level=logging.INFO)

USERS_FILE = "users.json"

# Шаги регистрации
REG_NAME, REG_ROLE, REG_CONTACT = range(3)

# Шаги создания проекта
PROJ_NAME, PROJ_DESC, PROJ_TEAM, PROJ_STACK, PROJ_FORMAT, PROJ_CONFIRM = range(3, 9)


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ───────────────────────────────────────────
# РЕГИСТРАЦИЯ
# ───────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    user_id = str(update.effective_user.id)

    if user_id in users:
        await update.message.reply_text(
            f"👋 С возвращением, {users[user_id]['name']}!\n\n"
            "📌 Команды:\n"
            "/newproject — создать пост о проекте\n"
            "/cancel — отменить действие"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Привет! Я помогу тебе найти команду для проекта.\n\n"
        "Сначала давай познакомимся.\n\n"
        "✏️ Как тебя зовут?"
    )
    return REG_NAME


async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text

    keyboard = [["Разработчик", "Дизайнер"], ["Маркетолог", "Продакт"], ["Другое"]]
    await update.message.reply_text(
        "Отлично! Кто ты по роли?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return REG_ROLE


async def reg_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["role"] = update.message.text

    await update.message.reply_text(
        "👌 Принято!\n\nУкажи свой Telegram username (например @username) "
        "или другой способ связи:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return REG_CONTACT


async def reg_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contact"] = update.message.text

    users = load_users()
    user_id = str(update.effective_user.id)
    users[user_id] = {
        "name": context.user_data["name"],
        "role": context.user_data["role"],
        "contact": context.user_data["contact"],
        "username": update.effective_user.username or "",
    }
    save_users(users)

    await update.message.reply_text(
        f"✅ Регистрация завершена!\n\n"
        f"👤 Имя: {context.user_data['name']}\n"
        f"💼 Роль: {context.user_data['role']}\n"
        f"📩 Контакт: {context.user_data['contact']}\n\n"
        f"Теперь ты можешь создать пост о своём проекте — /newproject 🚀"
    )
    return ConversationHandler.END


# ───────────────────────────────────────────
# СОЗДАНИЕ ПОСТА О ПРОЕКТЕ
# ───────────────────────────────────────────

async def new_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    user_id = str(update.effective_user.id)

    if user_id not in users:
        await update.message.reply_text(
            "⚠️ Сначала нужно зарегистрироваться — напиши /start"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🚀 Создаём пост о проекте!\n\n"
        "Отвечай на вопросы и я сформирую красивый пост.\n\n"
        "📌 Как называется твой проект?"
    )
    return PROJ_NAME


async def proj_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_name"] = update.message.text
    await update.message.reply_text(
        "💡 Опиши проект — что делаете, какую проблему решаете?\n\n"
        "(2–4 предложения)"
    )
    return PROJ_DESC


async def proj_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_desc"] = update.message.text
    await update.message.reply_text(
        "👥 Кого ищешь в команду?\n\n"
        "Например: Backend-разработчик (Python), UI/UX дизайнер"
    )
    return PROJ_TEAM


async def proj_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_team"] = update.message.text
    await update.message.reply_text(
        "🛠 Какой стек / направление?\n\n"
        "Например: React, FastAPI, PostgreSQL\n"
        "Или напиши «не важно» если не принципиально"
    )
    return PROJ_STACK


async def proj_stack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_stack"] = update.message.text

    keyboard = [["💰 Оплата", "📊 Доля в проекте"], ["🤝 Волонтёрство", "💬 Обсуждаемо"]]
    await update.message.reply_text(
        "Формат участия для команды?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return PROJ_FORMAT


async def proj_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["proj_format"] = update.message.text

    users = load_users()
    user_id = str(update.effective_user.id)
    user = users[user_id]

    contact = f"@{user['username']}" if user.get("username") else user["contact"]

    post = (
        f"🚀 *{context.user_data['proj_name']}*\n\n"
        f"💡 *Описание:*\n{context.user_data['proj_desc']}\n\n"
        f"👥 *Ищем в команду:*\n{context.user_data['proj_team']}\n\n"
        f"🛠 *Стек:* {context.user_data['proj_stack']}\n\n"
        f"💰 *Формат участия:* {context.user_data['proj_format']}\n\n"
        f"👤 *Автор:* {user['name']} — {user['role']}\n"
        f"📩 *Связаться:* {contact}"
    )

    context.user_data["final_post"] = post

    keyboard = [["✅ Опубликовать", "❌ Отменить"]]
    await update.message.reply_text(
        f"👀 Вот как будет выглядеть пост:\n\n{post}\n\n"
        "Публикуем в группу?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown",
    )
    return PROJ_CONFIRM


async def proj_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ Опубликовать":
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=context.user_data["final_post"],
            parse_mode="Markdown",
        )
        await update.message.reply_text(
            "🎉 Пост опубликован в группу!\n\n"
            "Удачи в поиске команды 💪\n\n"
            "Хочешь создать ещё один? — /newproject",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text(
            "❌ Публикация отменена.\n\nНапиши /newproject чтобы начать заново.",
            reply_markup=ReplyKeyboardRemove(),
        )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отменено ✋\n\nНапиши /start или /newproject чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ───────────────────────────────────────────
# ЗАПУСК
# ───────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    reg_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_role)],
            REG_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_contact)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    proj_handler = ConversationHandler(
        entry_points=[CommandHandler("newproject", new_project)],
        states={
            PROJ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_name)],
            PROJ_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_desc)],
            PROJ_TEAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_team)],
            PROJ_STACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_stack)],
            PROJ_FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_format)],
            PROJ_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, proj_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_handler)
    app.add_handler(proj_handler)

    print("✅ Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
