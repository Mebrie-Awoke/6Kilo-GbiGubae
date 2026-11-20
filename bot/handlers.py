"""User registration and super-admin commands."""
import asyncio
import logging
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.config import Settings
from bot.states import Registration
from bot.storage import JsonStore

logger = logging.getLogger(__name__)
router = Router()


def batch_keyboard(batches: tuple[str, ...]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=batch)] for batch in batches],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_only(settings: Settings, message: Message) -> bool:
    return bool(message.from_user and message.from_user.id == settings.super_admin_id)


def command_payload(message: Message) -> str:
    return (message.text or "").partition(" ")[2].strip()


def valid_target(target: str, settings: Settings) -> bool:
    return target.lower() == "all" or target in settings.batches


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, store: JsonStore):
    user = await store.get_user(message.from_user.id)
    if user:
        await state.clear()
        await message.answer(
            f"Welcome back, {escape(user['name'])}!\n"
            f"Your batch: {escape(user['batch'])}\n\n"
            "Use /profile to view your details or /edit_batch to change your batch.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await state.set_state(Registration.entering_name)
    await message.answer("Welcome! Please enter your full name.", reply_markup=ReplyKeyboardRemove())


@router.message(Registration.entering_name, F.text & ~F.text.startswith("/"))
async def collect_name(message: Message, state: FSMContext, settings: Settings):
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 80:
        await message.answer("Please enter a name between 2 and 80 characters.")
        return
    await state.update_data(name=name)
    await state.set_state(Registration.choosing_batch)
    await message.answer("Choose your batch:", reply_markup=batch_keyboard(settings.batches))


@router.message(Registration.choosing_batch, F.text & ~F.text.startswith("/"))
async def collect_batch(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    batch = (message.text or "").strip()
    if batch not in settings.batches:
        await message.answer("Please choose a batch using the keyboard.", reply_markup=batch_keyboard(settings.batches))
        return
    data = await state.get_data()
    name = data.get("name")
    if not name:
        await state.clear()
        await message.answer("Registration expired. Please use /start again.")
        return
    await store.save_user(message.from_user.id, name, batch)
    await state.clear()
    await message.answer(
        f"Registration complete!\nName: {escape(name)}\nBatch: {escape(batch)}\n\n"
        "You will now receive announcements for your batch.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("profile"))
@router.message(Command("my_batch"))
async def profile(message: Message, store: JsonStore):
    user = await store.get_user(message.from_user.id)
    if not user:
        await message.answer("You are not registered yet. Use /start.")
        return
    await message.answer(f"Name: {escape(user['name'])}\nBatch: {escape(user['batch'])}")


@router.message(Command("edit_batch"))
async def edit_batch(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    user = await store.get_user(message.from_user.id)
    if not user:
        await message.answer("Please use /start first.")
        return
    await state.update_data(name=user["name"])
    await state.set_state(Registration.choosing_batch)
    await message.answer("Choose your new batch:", reply_markup=batch_keyboard(settings.batches))


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Current action cancelled.", reply_markup=ReplyKeyboardRemove())


@router.message(Command("help"))
async def help_command(message: Message, settings: Settings):
    text = (
        "Available commands:\n"
        "/start — Register or restart\n"
        "/profile — View your profile\n"
        "/edit_batch — Change your batch\n"
        "/help — Show this help"
    )
    if message.from_user.id == settings.super_admin_id:
        text += (
            "\n\nAdministrator commands:\n"
            "/users — Count registered users\n"
            "/broadcast batch | message — Send now\n"
            "/schedule YYYY-MM-DD HH:MM | batch | message — Schedule\n"
            "/schedules — List pending schedules\n"
            "/cancel_schedule ID — Cancel a schedule"
        )
    await message.answer(text)


@router.message(Command("users"))
async def users_command(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("You are not authorized to use this command.")
        return
    users = await store.list_users()
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user["batch"] in counts:
            counts[user["batch"]] += 1
    lines = [f"Total registered: {len(users)}"]
    lines.extend(f"{batch}: {count}" for batch, count in counts.items())
    await message.answer("\n".join(lines))


async def send_to_target(message: Message, store: JsonStore, target: str, text: str) -> tuple[int, int]:
    recipients = await store.list_users(None if target.lower() == "all" else target)
    sent = 0
    failed = 0
    for recipient in recipients:
        try:
            await message.bot.send_message(recipient["telegram_id"], text, parse_mode=None)
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            failed += 1
            logger.exception("Immediate broadcast failed for Telegram user %s", recipient["telegram_id"])
    return sent, failed


@router.message(Command("broadcast"))
async def broadcast(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("You are not authorized to use this command.")
        return
    payload = command_payload(message)
    if "|" not in payload:
        await message.answer("Usage: /broadcast batch | message. Use 'all' to target everyone.")
        return
    target, text = (part.strip() for part in payload.split("|", 1))
    if not valid_target(target, settings) or not text or len(text) > 4096:
        await message.answer("Invalid batch or message. Messages must contain 1–4096 characters.")
        return
    sent, failed = await send_to_target(message, store, target, text)
    await message.answer(f"Broadcast finished.\nSent: {sent}\nFailed: {failed}")


@router.message(Command("schedule"))
async def schedule_message(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("You are not authorized to use this command.")
        return
    parts = [part.strip() for part in command_payload(message).split("|", 2)]
    if len(parts) != 3:
        await message.answer(
            "Usage:\n/schedule YYYY-MM-DD HH:MM | batch | message\n"
            "Example:\n/schedule 2026-11-22 09:00 | 1st Year | Class starts at 9 AM"
        )
        return
    time_text, target, text = parts
    if not valid_target(target, settings) or not text or len(text) > 4096:
        await message.answer("Invalid batch or message. Messages must contain 1–4096 characters.")
        return
    try:
        local_time = datetime.strptime(time_text, "%Y-%m-%d %H:%M")
        scheduled_at = local_time.replace(tzinfo=ZoneInfo(settings.timezone))
    except (ValueError, ZoneInfoNotFoundError):
        await message.answer("Invalid date/time or TIMEZONE. Use YYYY-MM-DD HH:MM.")
        return
    if scheduled_at <= datetime.now(scheduled_at.tzinfo):
        await message.answer("The scheduled time must be in the future.")
        return
    item = await store.create_schedule(
        batch=target, message=text, send_at=scheduled_at, created_by=message.from_user.id
    )
    await message.answer(
        f"Schedule created.\nID: {item['id']}\nTarget: {target}\n"
        f"Time: {scheduled_at.strftime('%Y-%m-%d %H:%M %Z')}"
    )


@router.message(Command("schedules"))
async def list_schedules(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("You are not authorized to use this command.")
        return
    schedules = await store.list_schedules()
    if not schedules:
        await message.answer("There are no pending scheduled messages.")
        return
    lines = ["Pending schedules:"]
    for item in schedules[:30]:
        when = datetime.fromisoformat(item["send_at"]).astimezone(ZoneInfo(settings.timezone))
        lines.append(f"#{item['id']} | {when:%Y-%m-%d %H:%M} | {item['batch']} | {item['message'][:60]}")
    await message.answer("\n".join(lines))


@router.message(Command("cancel_schedule"))
async def cancel_schedule(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("You are not authorized to use this command.")
        return
    try:
        schedule_id = int(command_payload(message))
    except ValueError:
        await message.answer("Usage: /cancel_schedule ID")
        return
    if await store.cancel_schedule(schedule_id):
        await message.answer(f"Schedule #{schedule_id} cancelled.")
    else:
        await message.answer("Pending schedule not found.")
