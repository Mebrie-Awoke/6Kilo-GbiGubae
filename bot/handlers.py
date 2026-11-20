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
from bot.ethiopian_calendar import format_ethiopian, parse_ethiopian_datetime
from bot.states import AdminBroadcast, Registration
from bot.storage import MongoStore

logger = logging.getLogger(__name__)
router = Router()


def is_admin(settings: Settings, user_id: int | None) -> bool:
    return bool(user_id and user_id == settings.super_admin_id)


def admin_only(settings: Settings, message: Message) -> bool:
    return is_admin(settings, message.from_user.id if message.from_user else None)


def command_payload(message: Message) -> str:
    return (message.text or "").partition(" ")[2].strip()


def normalize_batch(value: str, settings: Settings) -> str | None:
    """Accept canonical labels, numeric years, and legacy Amharic labels."""
    cleaned = " ".join(value.strip().casefold().split())
    aliases = {
        "1": "1st Year", "1st": "1st Year", "1st year": "1st Year", "1ኛ ዓመት": "1st Year",
        "2": "2nd Year", "2nd": "2nd Year", "2nd year": "2nd Year", "2ኛ ዓመት": "2nd Year",
        "3": "3rd Year", "3rd": "3rd Year", "3rd year": "3rd Year", "3ኛ ዓመት": "3rd Year",
        "4": "4th Year", "4th": "4th Year", "4th year": "4th Year", "4ኛ ዓመት": "4th Year",
        "5": "5th Year", "5th": "5th Year", "5th year": "5th Year", "5ኛ ዓመት": "5th Year",
        "6": "6th Year", "6th": "6th Year", "6th year": "6th Year", "6ኛ ዓመት": "6th Year",
    }
    candidate = aliases.get(cleaned, value.strip())
    return next((batch for batch in settings.batches if batch.casefold() == candidate.casefold()), None)


def valid_target(target: str, settings: Settings) -> bool:
    return target.casefold() == "all" or normalize_batch(target, settings) is not None



def display_batch(batch: str) -> str:
    return "All Members" if batch.casefold() == "all" else batch


def batch_keyboard(batches: tuple[str, ...]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=batch)] for batch in batches],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def member_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 My Profile", callback_data="member:profile"),
         InlineKeyboardButton(text="🎓 Change Academic Year", callback_data="member:batch")],
        [InlineKeyboardButton(text="ℹ️ Help", callback_data="member:help")],
    ])


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Overview", callback_data="admin:overview"),
         InlineKeyboardButton(text="👥 Members", callback_data="admin:members")],
        [InlineKeyboardButton(text="📣 New Announcement", callback_data="admin:broadcast"),
         InlineKeyboardButton(text="🗓 Scheduled Messages", callback_data="admin:schedules")],
        [InlineKeyboardButton(text="❔ Help", callback_data="admin:help")],
    ])


def target_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📢 All Members", callback_data="broadcast:target:all")]]
    rows.extend(
        [InlineKeyboardButton(text=f"🎓 {display_batch(batch)}", callback_data=f"broadcast:target:{index}")]
        for index, batch in enumerate(settings.batches)
    )
    rows.append([InlineKeyboardButton(text="✖ Cancel", callback_data="broadcast:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Send Announcement", callback_data="broadcast:confirm")],
        [InlineKeyboardButton(text="✏️ Edit", callback_data="broadcast:edit"),
         InlineKeyboardButton(text="✖ Cancel", callback_data="broadcast:cancel")],
    ])


async def show_admin_home(message: Message, state: FSMContext, store: MongoStore, settings: Settings) -> None:
    await state.clear()
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    await message.answer(
        "🛡 <b>6Kilo GbiGubae | Admin Workspace</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 Ethiopian date: <b>{format_ethiopian(datetime.now(ZoneInfo(settings.timezone)), ZoneInfo(settings.timezone))}</b>\n"
        f"👥 Registered members: <b>{len(users)}</b>\n"
        "Choose an action below to manage the community.",
        reply_markup=admin_menu(),
    )


async def show_member_home(message: Message, user: dict, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await message.answer(
        f"👋 <b>Welcome back, {escape(user['name'])}!</b>\n\n"
        f"🎓 Academic year: <b>{escape(user['batch'])}</b>\n"
        f"📅 Ethiopian date: <b>{format_ethiopian(datetime.now(ZoneInfo(settings.timezone)), ZoneInfo(settings.timezone))}</b>\n"
        "Your membership profile is active.",
        reply_markup=member_menu(),
    )


async def start_registration(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.entering_name)
    await message.answer(
        "👋 <b>Welcome to 6Kilo GbiGubae</b>\n\n"
        "Let's set up your membership profile.\n"
        "Please enter your full name.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, store: MongoStore, settings: Settings):
    user_id = message.from_user.id
    if is_admin(settings, user_id):
        await show_admin_home(message, state, store, settings)
        return
    user = await store.get_user(user_id)
    if user:
        await show_member_home(message, user, state, settings)
        return
    await start_registration(message, state)


@router.message(Command("admin"))
async def admin_home(message: Message, state: FSMContext, store: MongoStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ Access denied. This workspace is restricted to administrators.")
        return
    await show_admin_home(message, state, store, settings)


@router.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext, store: MongoStore, settings: Settings):
    if admin_only(settings, message):
        await show_admin_home(message, state, store, settings)
        return
    user = await store.get_user(message.from_user.id)
    if not user:
        await start_registration(message, state)
        return
    await show_member_home(message, user, state, settings)


@router.callback_query(F.data == "admin:overview")
async def admin_overview(callback: CallbackQuery, store: MongoStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user.get("batch") in counts:
            counts[user["batch"]] += 1
    lines = ["📊 <b>Community Overview</b>", "━━━━━━━━━━━━━━━━━━",
             f"Total registered members: <b>{len(users)}</b>", ""]
    lines.extend(f"• {escape(display_batch(batch))}: <b>{count}</b>" for batch, count in counts.items())
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:members")
async def admin_members(callback: CallbackQuery, store: MongoStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user.get("batch") in counts:
            counts[user["batch"]] += 1
    lines = ["👥 <b>Member Summary</b>", "━━━━━━━━━━━━━━━━━━",
             f"Registered members: <b>{len(users)}</b>"]
    lines.extend(f"• {escape(display_batch(batch))} — {count}" for batch, count in counts.items())
    lines.append("\nUse /users to view the member breakdown.")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:schedules")
async def admin_schedules(callback: CallbackQuery, store: MongoStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    schedules = await store.list_schedules()
    if not schedules:
        text = "🗓 <b>Scheduled Announcements</b>\n\nThere are no pending announcements."
    else:
        lines = ["🗓 <b>Pending Announcements</b>", "━━━━━━━━━━━━━━━━━━"]
        for item in schedules[:15]:
            when = datetime.fromisoformat(item["send_at"]).astimezone(ZoneInfo(settings.timezone))
            lines.append(
                f"#{item['id']} · {format_ethiopian(when, ZoneInfo(settings.timezone))} · "
                f"{escape(display_batch(item['batch']))}\n{escape(item['message'][:70])}"
            )
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:help")
async def admin_help(callback: CallbackQuery, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    text = (
        "❔ <b>Administrator Guide</b>\n\n"
        "• Overview — membership and academic-year statistics\n"
        "• Members — registered members by academic year\n"
        "• New Announcement — guided announcement workflow\n"
        "• Scheduled Messages — review pending deliveries\n\n"
        "Commands: /admin, /users, /broadcast, /schedule, "
        "/schedules, /cancel_schedule ID, /menu"
    )
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def begin_broadcast(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    await state.set_state(AdminBroadcast.choosing_target)
    await callback.message.edit_text(
        "📣 <b>New Announcement</b>\n\n"
        "Step 1 of 2 — Choose the audience for this announcement.",
        reply_markup=target_keyboard(settings),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:target:"))
async def choose_broadcast_target(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    if await state.get_state() != AdminBroadcast.choosing_target.state:
        await callback.answer("This announcement session has expired. Please start again.", show_alert=True)
        return
    selected = callback.data.rsplit(":", 1)[1]
    if selected == "all":
        target = "all"
        label = "All registered members"
    else:
        try:
            target = settings.batches[int(selected)]
        except (ValueError, IndexError):
            await callback.answer("The selected audience is invalid.", show_alert=True)
            return
        label = display_batch(target)
    await state.update_data(target=target, target_label=label)
    await state.set_state(AdminBroadcast.entering_message)
    await callback.message.edit_text(
        f"📣 <b>New Announcement</b>\nAudience: <b>{escape(label)}</b>\n\n"
        "Step 2 of 2 — Send the announcement text in your next message.\n"
        "You can send up to 4,096 characters. Use /cancel to stop."
    )
    await callback.answer()


@router.message(AdminBroadcast.entering_message, F.text & ~F.text.startswith("/"))
async def compose_broadcast(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 4096:
        await message.answer("Please send announcement text containing 1–4,096 characters.")
        return
    data = await state.get_data()
    await state.update_data(message=text)
    await state.set_state(AdminBroadcast.confirming)
    await message.answer(
        "🔎 <b>Review Announcement</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Audience: <b>{escape(data.get('target_label', 'Unknown'))}</b>\n\n"
        f"{escape(text)}\n\n"
        "Are you ready to send this announcement?",
        reply_markup=confirmation_keyboard(),
    )


@router.callback_query(F.data == "broadcast:edit")
async def edit_broadcast(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    if await state.get_state() != AdminBroadcast.confirming.state:
        await callback.answer("This announcement session has expired.", show_alert=True)
        return
    await state.set_state(AdminBroadcast.entering_message)
    await callback.message.edit_text("✏️ Send the revised announcement text. Use /cancel to stop.")
    await callback.answer()


@router.callback_query(F.data == "broadcast:confirm")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, store: MongoStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    if await state.get_state() != AdminBroadcast.confirming.state:
        await callback.answer("This announcement session has expired.", show_alert=True)
        return
    data = await state.get_data()
    target, text = data.get("target"), data.get("message")
    if not target or not text or not valid_target(target, settings):
        await state.clear()
        await callback.answer("Announcement details are incomplete. Please start again.", show_alert=True)
        return
    await callback.message.edit_text("⏳ <b>Sending announcement…</b>")
    sent, failed, total = await send_to_target(callback.message, store, target, text, settings)
    await state.clear()
    await callback.message.edit_text(
        "📬 <b>Delivery Report</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Audience: <b>{escape(data.get('target_label', target))}</b>\n"
        f"Recipients: <b>{total}</b>\n"
        f"Delivered: <b>{sent}</b>\n"
        f"Failed: <b>{failed}</b>",
        reply_markup=admin_menu(),
    )
    await callback.answer("Announcement workflow completed.")


@router.callback_query(F.data == "broadcast:cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext, settings: Settings, store: MongoStore):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("Access denied.", show_alert=True)
        return
    await state.clear()
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    await callback.message.edit_text(
        f"🛡 <b>Admin Workspace</b>\nRegistered members: <b>{len(users)}</b>",
        reply_markup=admin_menu(),
    )
    await callback.answer("Announcement cancelled.")


@router.callback_query(F.data == "member:profile")
async def member_profile(callback: CallbackQuery, store: MongoStore):
    user = await store.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Please complete registration first using /start.", show_alert=True)
        return
    await callback.message.answer(
        f"👤 <b>Your Membership Profile</b>\n\n"
        f"Name: {escape(user['name'])}\nAcademic year: {escape(user['batch'])}"
    )
    await callback.answer()


@router.callback_query(F.data == "member:batch")
async def member_change_batch(callback: CallbackQuery, state: FSMContext, store: MongoStore, settings: Settings):
    user = await store.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Please complete registration first using /start.", show_alert=True)
        return
    await state.update_data(name=user["name"])
    await state.set_state(Registration.choosing_batch)
    await callback.message.answer("🎓 <b>Select your new academic year</b>", reply_markup=batch_keyboard(settings.batches))
    await callback.answer()


@router.callback_query(F.data == "member:help")
async def member_help(callback: CallbackQuery):
    await callback.message.answer(
        "ℹ️ <b>Member Help</b>\n\n"
        "/start — Open your membership home\n"
        "/profile — View your membership profile\n"
        "/edit_batch — Change your academic year\n"
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
    await message.answer("🎓 <b>Select your academic year</b>", reply_markup=batch_keyboard(settings.batches))


@router.message(Registration.choosing_batch, F.text & ~F.text.startswith("/"))
async def collect_batch(message: Message, state: FSMContext, store: MongoStore, settings: Settings):
    batch = normalize_batch(message.text or "", settings)
    if batch is None:
        await message.answer(
            "Please choose an academic year using one of the buttons below. "
            "You can also type 1, 2, 3, 4, 5, or 6.",
            reply_markup=batch_keyboard(settings.batches),
        )
        return
    data = await state.get_data()
    name = data.get("name")
    if not name:
        await state.clear()
        await message.answer("Your registration session expired. Please start again with /start.")
        return
    await store.save_user(message.from_user.id, name, batch)
    await state.clear()
    await message.answer(
        "✅ <b>Registration Complete</b>\n\n"
        f"Name: <b>{escape(name)}</b>\nAcademic year: <b>{escape(batch)}</b>\n\n"
        "You will now receive announcements intended for your academic year.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Your membership menu:", reply_markup=member_menu())


@router.message(Command("profile"))
@router.message(Command("my_batch"))
async def profile(message: Message, store: MongoStore):
    user = await store.get_user(message.from_user.id)
    if not user:
        await message.answer("You are not registered yet. Use /start to register.")
        return
    await message.answer(f"👤 <b>{escape(user['name'])}</b>\n🎓 {escape(display_batch(user['batch']))}")


@router.message(Command("edit_batch"))
async def edit_batch(message: Message, state: FSMContext, store: MongoStore, settings: Settings):
    user = await store.get_user(message.from_user.id)
    if not user:
        await message.answer("Please register first using /start.")
        return
    await state.update_data(name=user["name"])
    await state.set_state(Registration.choosing_batch)
    await message.answer("🎓 <b>Select your new academic year</b>", reply_markup=batch_keyboard(settings.batches))


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext, settings: Settings, store: MongoStore):
    await state.clear()
    if admin_only(settings, message):
        await show_admin_home(message, state, store, settings)
    else:
        await message.answer("Your current action has been cancelled.", reply_markup=ReplyKeyboardRemove())


@router.message(Command("help"))
async def help_command(message: Message, settings: Settings):
    if admin_only(settings, message):
        await message.answer(
            "🛡 <b>Administrator Commands</b>\n\n"
            "/admin — Open the admin workspace\n"
            "/users — View membership statistics\n"
            "/broadcast — Send an announcement\n"
            "/schedule YYYY-MM-DD HH:MM | batch | message — Schedule using Ethiopian date (E.C.)\n"
            "/schedules — View scheduled messages\n"
            "/cancel_schedule ID — Cancel a scheduled message\n"
            "/menu — Open the admin workspace"
        )
    else:
        await message.answer(
            "ℹ️ <b>Member commands</b>\n\n"
            "/start — Open your membership home\n"
            "/profile — View your membership profile\n"
            "/edit_batch — Change your academic year\n"
            "/menu — Show the main menu\n"
            "/cancel — Cancel the current action"
        )


@router.message(Command("users"))
async def users_command(message: Message, store: MongoStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ Access denied. This command is restricted to administrators.")
        return
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user.get("batch") in counts:
            counts[user["batch"]] += 1
    lines = ["👥 <b>Member Report</b>", "━━━━━━━━━━━━━━━━━━",
             f"Total registered: <b>{len(users)}</b>", ""]
    lines.extend(f"• {escape(display_batch(batch))}: <b>{count}</b>" for batch, count in counts.items())
    await message.answer("\n".join(lines), reply_markup=admin_menu())


async def send_to_target(message: Message, store: MongoStore, target: str, text: str, settings: Settings) -> tuple[int, int, int]:
    recipients = [
        user for user in await store.list_users(None if target.lower() == "all" else target)
        if user["telegram_id"] != settings.super_admin_id
    ]
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
        await message.answer("⛔ Access denied. This command is restricted to administrators.")
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
        "📣 <b>Announcement Composer</b>\n\n"
        "Step 1 of 2 — Choose who should receive this announcement.",
        reply_markup=target_keyboard(settings),
    )


@router.message(Command("schedule"))
async def schedule_message(message: Message, store: MongoStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ Access denied. This command is restricted to administrators.")
        return
    parts = [part.strip() for part in command_payload(message).split("|", 2)]
    if len(parts) != 3:
        await message.answer(
            "🗓 <b>Schedule an Announcement</b>\n\n"
            "Format: /schedule YYYY-MM-DD HH:MM | batch | message (Ethiopian calendar)\n"
            "Use 'all' to target every registered member.\n"
            "Example: /schedule 2019-03-13 09:00 | 1st Year | Class starts at 9 AM\n"
            "ወራት: መስከረም፣ ጥቅምት፣ ኅዳር፣ ታኅሣሥ፣ ጥር፣ የካቲት፣ መጋቢት፣ ሚያዝያ፣ ግንቦት፣ ሰኔ፣ ሐምሌ፣ ነሐሴ፣ ጳጉሜ።"
        )
        return
    time_text, target, text = parts
    if not valid_target(target, settings) or not text or len(text) > 4096:
        await message.answer("Invalid audience or message. The message must contain 1–4,096 characters.")
        return
    if target.casefold() != "all":
        target = normalize_batch(target, settings) or target
    try:
        scheduled_at = parse_ethiopian_datetime(time_text, ZoneInfo(settings.timezone))
    except (ValueError, ZoneInfoNotFoundError):
        await message.answer("Invalid Ethiopian date or time. Use YYYY-MM-DD HH:MM (E.C.).")
        return
    if scheduled_at <= datetime.now(scheduled_at.tzinfo):
        await message.answer("The scheduled time must be in the future.")
        return
    item = await store.create_schedule(
        batch=target, message=text, send_at=scheduled_at, created_by=message.from_user.id
    )
    await message.answer(
        "✅ <b>Announcement Scheduled</b>\n\n"
        f"Schedule ID: <b>#{item['id']}</b>\nAudience: <b>{escape(display_batch(target))}</b>\n"
        f"Scheduled for: <b>{format_ethiopian(scheduled_at, ZoneInfo(settings.timezone))}</b>"
    )


@router.message(Command("schedules"))
async def list_schedules(message: Message, store: MongoStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ Access denied. This command is restricted to administrators.")
        return
    schedules = await store.list_schedules()
    if not schedules:
        await message.answer("🗓 <b>Scheduled Announcements</b>\n\nThere are no pending announcements.")
        return
    lines = ["🗓 <b>Pending Announcements</b>", "━━━━━━━━━━━━━━━━━━"]
    for item in schedules[:30]:
        when = datetime.fromisoformat(item["send_at"]).astimezone(ZoneInfo(settings.timezone))
        lines.append(
            f"#{item['id']} · {format_ethiopian(when, ZoneInfo(settings.timezone))} · {escape(display_batch(item['batch']))}\n"
            f"{escape(item['message'][:80])}"
        )
    await message.answer("\n\n".join(lines), reply_markup=admin_menu())


@router.message(Command("cancel_schedule"))
async def cancel_schedule(message: Message, store: MongoStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ Access denied. This command is restricted to administrators.")
        return
    try:
        schedule_id = int(command_payload(message))
    except ValueError:
        await message.answer("Usage: /cancel_schedule ID")
        return
    if await store.cancel_schedule(schedule_id):
        await message.answer(f"✅ Schedule #{schedule_id} has been cancelled.")
    else:
        await message.answer("No pending announcement was found with that ID.")
