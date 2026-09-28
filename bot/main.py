from __future__ import annotations

import logging
from datetime import UTC, datetime

from telegram import Chat, ChatMember, Update, User
from telegram.constants import ParseMode
from telegram.error import BadRequest, ChatMigrated, Forbidden
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import Config, load_config
from bot.report import build_reminder, build_stats, local_day, split_message
from bot.storage import Storage

log = logging.getLogger("english_bot")

TELEGRAM_SERVICE_USER_ID = 777000
GONE_STATUSES = {ChatMember.LEFT, ChatMember.BANNED}

HELP_TEXT = (
    "Every day at {time} I remind the group to write a <b>daily update</b> — how your day went.\n"
    "Any message you send in the group during the day counts as your update.\n"
    "The reminder also lists who has gone {days}+ days without an update.\n\n"
    "/stats — who has gone {days}+ days without an update"
)


def storage(context: ContextTypes.DEFAULT_TYPE) -> Storage:
    return context.bot_data["storage"]


def config(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.bot_data["config"]


def is_person(user: User | None) -> bool:
    return user is not None and not user.is_bot and user.id != TELEGRAM_SERVICE_USER_ID


def today(context: ContextTypes.DEFAULT_TYPE):
    return local_day(datetime.now(UTC), config(context).timezone)


def remember(context: ContextTypes.DEFAULT_TYPE, chat: Chat, user: User) -> None:
    store = storage(context)
    store.upsert_chat(chat.id, chat.title)
    store.upsert_member(chat.id, user.id, user.full_name, user.username, today(context))


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or not is_person(user) or message.sender_chat is not None:
        return
    remember(context, message.chat, user)
    day = local_day(message.date, config(context).timezone)
    storage(context).record_update(message.chat.id, user.id, day)


async def on_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = message.left_chat_member
    if user is not None:
        storage(context).deactivate_member(message.chat.id, user.id)


async def on_migrate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message.migrate_to_chat_id:
        storage(context).migrate_chat(message.chat.id, message.migrate_to_chat_id)


async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    change = update.chat_member
    member = change.new_chat_member
    gone = member.status in GONE_STATUSES or (
        member.status == ChatMember.RESTRICTED and not getattr(member, "is_member", True)
    )
    if gone:
        storage(context).deactivate_member(change.chat.id, member.user.id)


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    change = update.my_chat_member
    if change.chat.type not in (Chat.GROUP, Chat.SUPERGROUP):
        return
    status = change.new_chat_member.status
    if status in GONE_STATUSES:
        storage(context).deactivate_chat(change.chat.id)
        log.info("removed from chat %s", change.chat.id)
    else:
        storage(context).upsert_chat(change.chat.id, change.chat.title)
        log.info("added to chat %s (%s)", change.chat.id, change.chat.title)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = config(context)
    text = HELP_TEXT.format(time=cfg.reminder_time.strftime("%H:%M"), days=cfg.min_missed_days)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    day = today(context)
    text = build_stats(
        storage(context).active_members(chat.id, day), day, config(context).min_missed_days
    )
    for chunk in split_message(text):
        await update.effective_message.reply_text(chunk, parse_mode=ParseMode.HTML)


async def send_text(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
    for chunk in split_message(text):
        await context.bot.send_message(chat_id, chunk, parse_mode=ParseMode.HTML)


async def deliver_reminder(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
    store = storage(context)
    for _ in range(2):
        try:
            await send_text(context, chat_id, text)
            log.info("reminder sent to %s", chat_id)
            return
        except ChatMigrated as exc:
            store.migrate_chat(chat_id, exc.new_chat_id)
            chat_id = exc.new_chat_id
        except Forbidden as exc:
            store.deactivate_chat(chat_id)
            log.warning("chat %s deactivated: %s", chat_id, exc)
            return
        except BadRequest as exc:
            if "chat not found" in exc.message.lower():
                store.deactivate_chat(chat_id)
                log.warning("chat %s deactivated: %s", chat_id, exc)
            else:
                log.exception("failed to send reminder to %s", chat_id)
            return
    log.error("gave up on reminder for %s after migration", chat_id)


async def send_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    store = storage(context)
    day = today(context)
    chats = store.active_chats()
    log.info("daily reminder for %d chat(s), day %s", len(chats), day)
    for chat_id in chats:
        text = build_reminder(
            store.active_members(chat_id, day), day, config(context).min_missed_days
        )
        try:
            await deliver_reminder(context, chat_id, text)
        except Exception:
            log.exception("failed to send reminder to %s", chat_id)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("update failed: %s", update, exc_info=context.error)


def build_application(cfg: Config) -> Application:
    app = Application.builder().token(cfg.token).build()
    app.bot_data["config"] = cfg
    app.bot_data["storage"] = Storage(cfg.db_path)

    groups = filters.ChatType.GROUPS
    app.add_handler(CommandHandler(["start", "help"], cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats, filters=groups))
    app.add_handler(MessageHandler(groups & filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_member))
    app.add_handler(MessageHandler(groups & filters.StatusUpdate.MIGRATE, on_migrate))
    app.add_handler(
        MessageHandler(
            groups & ~filters.COMMAND & ~filters.StatusUpdate.ALL & ~filters.IS_AUTOMATIC_FORWARD,
            on_message,
        )
    )
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_error_handler(on_error)

    app.job_queue.run_daily(send_reminders, time=cfg.reminder_time, name="daily-reminder")
    return app


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = load_config()
    app = build_application(cfg)
    log.info("starting, reminder at %s %s", cfg.reminder_time.strftime("%H:%M"), cfg.timezone)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
