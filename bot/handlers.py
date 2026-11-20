"""Member experience and guided super-admin workflows for 6Kilo GbiGubae."""
import asyncio
import logging
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from bot.config import Settings
from bot.states import AdminBroadcast, Registration
from bot.storage import JsonStore

logger = logging.getLogger(__name__)
router = Router()


def is_admin(settings: Settings, user_id: int | None) -> bool:
    return bool(user_id and user_id == settings.super_admin_id)


def admin_only(settings: Settings, message: Message) -> bool:
    return is_admin(settings, message.from_user.id if message.from_user else None)


def command_payload(message: Message) -> str:
    return (message.text or "").partition(" ")[2].strip()


def valid_target(target: str, settings: Settings) -> bool:
    return target.lower() == "all" or target in settings.batches


def batch_keyboard(batches: tuple[str, ...]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=batch)] for batch in batches],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def member_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 My profile", callback_data="member:profile"),
         InlineKeyboardButton(text="🎓 Change batch", callback_data="member:batch")],
        [InlineKeyboardButton(text="ℹ️ Help", callback_data="member:help")],
    ])


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Overview", callback_data="admin:overview"),
         InlineKeyboardButton(text="👥 Members", callback_data="admin:members")],
        [InlineKeyboardButton(text="📣 New announcement", callback_data="admin:broadcast"),
         InlineKeyboardButton(text="🗓 Schedules", callback_data="admin:schedules")],
        [InlineKeyboardButton(text="❔ Help", callback_data="admin:help")],
    ])


def target_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📢 All members", callback_data="broadcast:target:all")]]
    rows.extend(
        [InlineKeyboardButton(text=f"🎓 {batch}", callback_data=f"broadcast:target:{index}")]
        for index, batch in enumerate(settings.batches)
    )
    rows.append([InlineKeyboardButton(text="✖ Cancel", callback_data="broadcast:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Send announcement", callback_data="broadcast:confirm")],
        [InlineKeyboardButton(text="✏️ Edit message", callback_data="broadcast:edit"),
         InlineKeyboardButton(text="✖ Cancel", callback_data="broadcast:cancel")],
    ])


async def show_admin_home(message: Message, state: FSMContext, store: JsonStore) -> None:
    await state.clear()
    users = await store.list_users()
    await message.answer(
        "🛡 <b>6Kilo GbiGubae | Admin workspace</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 Registered members: <b>{len(users)}</b>\n"
        "Choose an operation below.",
        reply_markup=admin_menu(),
    )


async def show_member_home(message: Message, user: dict, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"👋 Welcome back, <b>{escape(user['name'])}</b>!\n\n"
        f"🎓 Batch: <b>{escape(user['batch'])}</b>\n"
        "Your community account is ready.",
        reply_markup=member_menu(),
    )


async def start_registration(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.entering_name)
    await message.answer(
        "👋 <b>Welcome to 6Kilo GbiGubae</b>\n\n"
        "Let's set up your community profile.\n"
        "Please enter your full name.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    user_id = message.from_user.id
    if is_admin(settings, user_id):
        await show_admin_home(message, state, store)
        return
    user = await store.get_user(user_id)
    if user:
        await show_member_home(message, user, state)
        return
    await start_registration(message, state)


@router.message(Command("admin"))
async def admin_home(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ This workspace is restricted to administrators.")
        return
    await show_admin_home(message, state, store)


@router.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    if admin_only(settings, message):
        await show_admin_home(message, state, store)
        return
    user = await store.get_user(message.from_user.id)
    if not user:
        await start_registration(message, state)
        return
    await show_member_home(message, user, state)


@router.callback_query(F.data == "admin:overview")
async def admin_overview(callback: CallbackQuery, store: JsonStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return
    users = await store.list_users()
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user.get("batch") in counts:
            counts[user["batch"]] += 1
    lines = ["📊 <b>Community overview</b>", "━━━━━━━━━━━━━━━━━━",
             f"Total members: <b>{len(users)}</b>", ""]
    lines.extend(f"• {escape(batch)}: <b>{count}</b>" for batch, count in counts.items())
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:members")
async def admin_members(callback: CallbackQuery, store: JsonStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return
    users = await store.list_users()
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user.get("batch") in counts:
            counts[user["batch"]] += 1
    lines = ["👥 <b>Member directory summary</b>", "━━━━━━━━━━━━━━━━━━",
             f"Registered: <b>{len(users)}</b>"]
    lines.extend(f"• {escape(batch)} — {count}" for batch, count in counts.items())
    lines.append("\nUse /users for the detailed count.")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:schedules")
async def admin_schedules(callback: CallbackQuery, store: JsonStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return
    schedules = await store.list_schedules()
    if not schedules:
        text = "🗓 <b>Scheduled announcements</b>\n\nNo pending announcements."
    else:
        lines = ["🗓 <b>Pending announcements</b>", "━━━━━━━━━━━━━━━━━━"]
        for item in schedules[:15]:
            when = datetime.fromisoformat(item["send_at"]).astimezone(ZoneInfo(settings.timezone))
            lines.append(
                f"#{item['id']} · {when:%d %b %Y, %H:%M} · "
                f"{escape(item['batch'])}\n{escape(item['message'][:70])}"
            )
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:help")
async def admin_help(callback: CallbackQuery, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return
    text = (
        "❔ <b>Administrator guide</b>\n\n"
        "• Overview — membership and batch statistics\n"
        "• Members — member totals by batch\n"
        "• New announcement — guided message composer\n"
        "• Schedules — view pending deliveries\n\n"
        "Commands: /admin, /users, /broadcast, /schedule, "
        "/schedules, /cancel_schedule ID, /menu"
    )
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def begin_broadcast(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return
    await state.set_state(AdminBroadcast.choosing_target)
    await callback.message.edit_text(
        "📣 <b>New announcement</b>\n\n"
        "Step 1 of 2 — choose the audience.",
        reply_markup=target_keyboard(settings),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:target:"))
async def choose_broadcast_target(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return
    if await state.get_state() != AdminBroadcast.choosing_target.state:
        await callback.answer("This announcement session has expired. Start again.", show_alert=True)
        return
    selected = callback.data.rsplit(":", 1)[1]
    if selected == "all":
        target = "all"
        label = "All registered members"
    else:
        try:
            target = settings.batches[int(selected)]
        except (ValueError, IndexError):
            await callback.answer("Invalid audience.", show_alert=True)
            return
        label = target
    await state.update_data(target=target, target_label=label)
    await state.set_state(AdminBroadcast.entering_message)
    await callback.message.edit_text(
        f"📣 <b>New announcement</b>\nAudience: <b>{escape(label)}</b>\n\n"
        "Step 2 of 2 — send the announcement text in your next message.\n"
        "You can send up to 4,096 characters. Use /cancel to stop."
    )
    await callback.answer()


@router.message(AdminBroadcast.entering_message, F.text & ~F.text.startswith("/"))
async def compose_broadcast(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 4096:
        await message.answer("Please send a message containing 1–4,096 characters.")
        return
    data = await state.get_data()
    await state.update_data(message=text)
    await state.set_state(AdminBroadcast.confirming)
    await message.answer(
        "🔎 <b>Review announcement</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Audience: <b>{escape(data.get('target_label', 'Unknown'))}</b>\n\n"
        f"{escape(text)}\n\n"
        "Send this announcement now?",
        reply_markup=confirmation_keyboard(),
    )


@router.callback_query(F.data == "broadcast:edit")
async def edit_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin_from_callback(callback):
        await callback.answer("Not authorized.", show_alert=True)
        return
    if await state.get_state() != AdminBroadcast.confirming.state:
        await callback.answer("This announcement session has expired.", show_alert=True)
        return
    await state.set_state(AdminBroadcast.entering_message)
    await callback.message.edit_text("✏️ Send the revised announcement text. Use /cancel to stop.")
    await callback.answer()


def is_admin_from_callback(callback: CallbackQuery) -> bool:
    # Callback authorization is also checked against settings in each action handler.
    return bool(callback.from_user)


@router.callback_query(F.data == "broadcast:confirm")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, store: JsonStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return
    if await state.get_state() != AdminBroadcast.confirming.state:
        await callback.answer("This announcement session has expired.", show_alert=True)
        return
    data = await state.get_data()
    target, text = data.get("target"), data.get("message")
    if not target or not text or not valid_target(target, settings):
        await state.clear()
        await callback.answer("Announcement details are incomplete. Start again.", show_alert=True)
        return
    await callback.message.edit_text("⏳ <b>Sending announcement…</b>")
    sent, failed, total = await send_to_target(callback.message, store, target, text)
    await state.clear()
    await callback.message.edit_text(
        "📬 <b>Delivery report</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Audience: <b>{escape(data.get('target_label', target))}</b>\n"
        f"Recipients: <b>{total}</b>\n"
        f"Delivered: <b>{sent}</b>\n"
        f"Failed: <b>{failed}</b>",
        reply_markup=admin_menu(),
    )
    await callback.answer("Announcement processed.")


@router.callback_query(F.data == "broadcast:cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext, settings: Settings, store: JsonStore):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return
    await state.clear()
    users = await store.list_users()
    await callback.message.edit_text(
        f"🛡 <b>Admin workspace</b>\nRegistered members: <b>{len(users)}</b>",
        reply_markup=admin_menu(),
    )
    await callback.answer("Announcement cancelled.")


@router.callback_query(F.data == "member:profile")
async def member_profile(callback: CallbackQuery, store: JsonStore):
    user = await store.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Please register with /start first.", show_alert=True)
        return
    await callback.message.answer(
        f"👤 <b>Your community profile</b>\n\n"
        f"Name: {escape(user['name'])}\nBatch: {escape(user['batch'])}"
    )
    await callback.answer()


@router.callback_query(F.data == "member:batch")
async def member_change_batch(callback: CallbackQuery, state: FSMContext, store: JsonStore, settings: Settings):
    user = await store.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Please register with /start first.", show_alert=True)
        return
    await state.update_data(name=user["name"])
    await state.set_state(Registration.choosing_batch)
    await callback.message.answer("🎓 Select your new batch:", reply_markup=batch_keyboard(settings.batches))
    await callback.answer()


@router.callback_query(F.data == "member:help")
async def member_help(callback: CallbackQuery):
    await callback.message.answer(
        "ℹ️ <b>Community help</b>\n\n"
        "/start — Open your community home\n"
        "/profile — View your profile\n"
        "/edit_batch — Change your batch\n"
        "/menu — Show the main menu\n"
        "/cancel — Cancel the current action"
    )
    await callback.answer()


@router.message(Registration.entering_name, F.text & ~F.text.startswith("/"))
async def collect_name(message: Message, state: FSMContext, settings: Settings):
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 80:
        await message.answer("Please enter a name between 2 and 80 characters.")
        return
    await state.update_data(name=name)
    await state.set_state(Registration.choosing_batch)
    await message.answer("🎓 Choose your batch:", reply_markup=batch_keyboard(settings.batches))


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
        await message.answer("Your registration session expired. Please use /start again.")
        return
    await store.save_user(message.from_user.id, name, batch)
    await state.clear()
    await message.answer(
        "✅ <b>Registration complete</b>\n\n"
        f"Name: <b>{escape(name)}</b>\nBatch: <b>{escape(batch)}</b>\n\n"
        "You're now subscribed to announcements for your batch.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Your community menu:", reply_markup=member_menu())


@router.message(Command("profile"))
@router.message(Command("my_batch"))
async def profile(message: Message, store: JsonStore):
    user = await store.get_user(message.from_user.id)
    if not user:
        await message.answer("You are not registered yet. Use /start.")
        return
    await message.answer(f"👤 <b>{escape(user['name'])}</b>\n🎓 {escape(user['batch'])}")


@router.message(Command("edit_batch"))
async def edit_batch(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    user = await store.get_user(message.from_user.id)
    if not user:
        await message.answer("Please use /start first.")
        return
    await state.update_data(name=user["name"])
    await state.set_state(Registration.choosing_batch)
    await message.answer("🎓 Choose your new batch:", reply_markup=batch_keyboard(settings.batches))


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext, settings: Settings, store: JsonStore):
    await state.clear()
    if admin_only(settings, message):
        await show_admin_home(message, state, store)
    else:
        await message.answer("Action cancelled.", reply_markup=ReplyKeyboardRemove())


@router.message(Command("help"))
async def help_command(message: Message, settings: Settings):
    if admin_only(settings, message):
        await message.answer(
            "🛡 <b>Administrator commands</b>\n\n"
            "/admin — Open admin workspace\n"
            "/users — Member statistics\n"
            "/broadcast — Guided announcement composer\n"
            "/schedule YYYY-MM-DD HH:MM | batch | message — Schedule a message\n"
            "/schedules — View pending schedules\n"
            "/cancel_schedule ID — Cancel a schedule\n"
            "/menu — Open workspace"
        )
    else:
        await message.answer(
            "ℹ️ <b>Member commands</b>\n\n"
            "/start — Open your community home\n"
            "/profile — View your profile\n"
            "/edit_batch — Change your batch\n"
            "/menu — Show the main menu\n"
            "/cancel — Cancel the current action"
        )


@router.message(Command("users"))
async def users_command(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ This command is restricted to administrators.")
        return
    users = await store.list_users()
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user.get("batch") in counts:
            counts[user["batch"]] += 1
    lines = ["👥 <b>Membership report</b>", "━━━━━━━━━━━━━━━━━━",
             f"Total registered: <b>{len(users)}</b>", ""]
    lines.extend(f"• {escape(batch)}: <b>{count}</b>" for batch, count in counts.items())
    await message.answer("\n".join(lines), reply_markup=admin_menu())


async def send_to_target(message: Message, store: JsonStore, target: str, text: str) -> tuple[int, int, int]:
    recipients = await store.list_users(None if target.lower() == "all" else target)
    sent = failed = 0
    for recipient in recipients:
        try:
            await message.bot.send_message(recipient["telegram_id"], text, parse_mode=None)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
            logger.exception("Announcement delivery failed for Telegram user %s", recipient["telegram_id"])
    return sent, failed, len(recipients)


@router.message(Command("broadcast"))
async def broadcast(message: Message, state: FSMContext, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ This command is restricted to administrators.")
        return
    payload = command_payload(message)
    if payload:
        await message.answer(
            "The command now uses a guided workflow. Send /broadcast without arguments, "
            "then choose an audience and compose your announcement."
        )
        return
    await state.set_state(AdminBroadcast.choosing_target)
    await message.answer(
        "📣 <b>Announcement composer</b>\n\n"
        "Step 1 of 2 — select who should receive your announcement.",
        reply_markup=target_keyboard(settings),
    )


@router.message(Command("schedule"))
async def schedule_message(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ This command is restricted to administrators.")
        return
    parts = [part.strip() for part in command_payload(message).split("|", 2)]
    if len(parts) != 3:
        await message.answer(
            "🗓 <b>Schedule an announcement</b>\n\n"
            "Format: /schedule YYYY-MM-DD HH:MM | batch | message\n"
            "Use 'all' for every registered member.\n"
            "Example: /schedule 2026-11-22 09:00 | 1st Year | Class starts at 9 AM"
        )
        return
    time_text, target, text = parts
    if not valid_target(target, settings) or not text or len(text) > 4096:
        await message.answer("Invalid audience or message. Message length must be 1–4,096 characters.")
        return
    try:
        local_time = datetime.strptime(time_text, "%Y-%m-%d %H:%M")
        scheduled_at = local_time.replace(tzinfo=ZoneInfo(settings.timezone))
    except (ValueError, ZoneInfoNotFoundError):
        await message.answer("Invalid date/time or timezone. Use YYYY-MM-DD HH:MM.")
        return
    if scheduled_at <= datetime.now(scheduled_at.tzinfo):
        await message.answer("The scheduled time must be in the future.")
        return
    item = await store.create_schedule(
        batch=target, message=text, send_at=scheduled_at, created_by=message.from_user.id
    )
    await message.answer(
        "✅ <b>Announcement scheduled</b>\n\n"
        f"Reference: <b>#{item['id']}</b>\nAudience: <b>{escape(target)}</b>\n"
        f"Time: <b>{scheduled_at.strftime('%d %b %Y, %H:%M %Z')}</b>"
    )


@router.message(Command("schedules"))
async def list_schedules(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ This command is restricted to administrators.")
        return
    schedules = await store.list_schedules()
    if not schedules:
        await message.answer("🗓 <b>Scheduled announcements</b>\n\nNo pending announcements.")
        return
    lines = ["🗓 <b>Pending announcements</b>", "━━━━━━━━━━━━━━━━━━"]
    for item in schedules[:30]:
        when = datetime.fromisoformat(item["send_at"]).astimezone(ZoneInfo(settings.timezone))
        lines.append(
            f"#{item['id']} · {when:%d %b %Y, %H:%M} · {escape(item['batch'])}\n"
            f"{escape(item['message'][:80])}"
        )
    await message.answer("\n\n".join(lines), reply_markup=admin_menu())


@router.message(Command("cancel_schedule"))
async def cancel_schedule(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ This command is restricted to administrators.")
        return
    try:
        schedule_id = int(command_payload(message))
    except ValueError:
        await message.answer("Usage: /cancel_schedule ID")
        return
    if await store.cancel_schedule(schedule_id):
        await message.answer(f"✅ Scheduled announcement #{schedule_id} cancelled.")
    else:
        await message.answer("No pending scheduled announcement was found with that ID.")
