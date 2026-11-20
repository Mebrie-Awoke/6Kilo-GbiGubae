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



def display_batch(batch: str) -> str:
    labels = {"1st Year": "1ኛ ዓመት", "2nd Year": "2ኛ ዓመት", "3rd Year": "3ኛ ዓመት", "4th Year": "4ኛ ዓመት", "5th Year": "5ኛ ዓመት", "6th Year": "6ኛ ዓመት"}
    return labels.get(batch, batch)


def batch_keyboard(batches: tuple[str, ...]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=display_batch(batch))] for batch in batches],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def member_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 መገለጫዬ", callback_data="member:profile"),
         InlineKeyboardButton(text="🎓 የትምህርት ዓመት ቀይር", callback_data="member:batch")],
        [InlineKeyboardButton(text="ℹ️ እገዛ", callback_data="member:help")],
    ])


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 አጠቃላይ እይታ", callback_data="admin:overview"),
         InlineKeyboardButton(text="👥 አባላት", callback_data="admin:members")],
        [InlineKeyboardButton(text="📣 አዲስ ማስታወቂያ", callback_data="admin:broadcast"),
         InlineKeyboardButton(text="🗓 የታቀዱ መልዕክቶች", callback_data="admin:schedules")],
        [InlineKeyboardButton(text="❔ እገዛ", callback_data="admin:help")],
    ])


def target_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📢 ለሁሉም አባላት", callback_data="broadcast:target:all")]]
    rows.extend(
        [InlineKeyboardButton(text=f"🎓 {display_batch(batch)}", callback_data=f"broadcast:target:{index}")]
        for index, batch in enumerate(settings.batches)
    )
    rows.append([InlineKeyboardButton(text="✖ ሰርዝ", callback_data="broadcast:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ማስታወቂያውን ላክ", callback_data="broadcast:confirm")],
        [InlineKeyboardButton(text="✏️ አስተካክል", callback_data="broadcast:edit"),
         InlineKeyboardButton(text="✖ ሰርዝ", callback_data="broadcast:cancel")],
    ])


async def show_admin_home(message: Message, state: FSMContext, store: JsonStore, settings: Settings) -> None:
    await state.clear()
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    await message.answer(
        "🛡 <b>6ኪሎ ግቢጉባኤ | የአስተዳዳሪ ማዕከል</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 የዛሬ ቀን: <b>{format_ethiopian(datetime.now(ZoneInfo(settings.timezone)), ZoneInfo(settings.timezone))}</b>\n"
        f"👥 የተመዘገቡ አባላት: <b>{len(users)}</b>\n"
        "ከታች ካሉት አማራጮች ይምረጡ።",
        reply_markup=admin_menu(),
    )


async def show_member_home(message: Message, user: dict, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await message.answer(
        f"👋 እንኳን በደህና ተመለሱ፣ <b>{escape(user['name'])}</b>!\n\n"
        f"🎓 የትምህርት ዓመት: <b>{escape(user['batch'])}</b>\n"
        f"📅 የዛሬ ቀን: <b>{format_ethiopian(datetime.now(ZoneInfo(settings.timezone)), ZoneInfo(settings.timezone))}</b>\n"
        "የአባልነት መለያዎ ዝግጁ ነው።",
        reply_markup=member_menu(),
    )


async def start_registration(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.entering_name)
    await message.answer(
        "👋 <b>ወደ 6ኪሎ ግቢጉባኤ እንኳን በደህና መጡ!</b>\n\n"
        "የአባልነት መረጃዎን እናዘጋጅ።\n"
        "እባክዎ ሙሉ ስምዎን ያስገቡ።",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
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
async def admin_home(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ ይህ የሥራ ቦታ ለአስተዳዳሪዎች ብቻ የተፈቀደ ነው።")
        return
    await show_admin_home(message, state, store, settings)


@router.message(Command("menu"))
async def menu_command(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    if admin_only(settings, message):
        await show_admin_home(message, state, store, settings)
        return
    user = await store.get_user(message.from_user.id)
    if not user:
        await start_registration(message, state)
        return
    await show_member_home(message, user, state, settings)


@router.callback_query(F.data == "admin:overview")
async def admin_overview(callback: CallbackQuery, store: JsonStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("ፈቃድ የለዎትም።", show_alert=True)
        return
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user.get("batch") in counts:
            counts[user["batch"]] += 1
    lines = ["📊 <b>የማኅበረሰቡ አጠቃላይ ሁኔታ</b>", "━━━━━━━━━━━━━━━━━━",
             f"ጠቅላላ አባላት: <b>{len(users)}</b>", ""]
    lines.extend(f"• {escape(display_batch(batch))}: <b>{count}</b>" for batch, count in counts.items())
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:members")
async def admin_members(callback: CallbackQuery, store: JsonStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("ፈቃድ የለዎትም።", show_alert=True)
        return
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user.get("batch") in counts:
            counts[user["batch"]] += 1
    lines = ["👥 <b>የአባላት ማጠቃለያ</b>", "━━━━━━━━━━━━━━━━━━",
             f"የተመዘገቡ: <b>{len(users)}</b>"]
    lines.extend(f"• {escape(display_batch(batch))} — {count}" for batch, count in counts.items())
    lines.append("\nUse /users for the detailed count.")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:schedules")
async def admin_schedules(callback: CallbackQuery, store: JsonStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("ፈቃድ የለዎትም።", show_alert=True)
        return
    schedules = await store.list_schedules()
    if not schedules:
        text = "🗓 <b>የታቀዱ ማስታወቂያዎች</b>\n\nለመላክ የሚጠብቅ ማስታወቂያ የለም።"
    else:
        lines = ["🗓 <b>ለመላክ የሚጠብቁ ማስታወቂያዎች</b>", "━━━━━━━━━━━━━━━━━━"]
        for item in schedules[:15]:
            when = datetime.fromisoformat(item["send_at"]).astimezone(ZoneInfo(settings.timezone))
            lines.append(
                f"#{item['id']} · {format_ethiopian(when, ZoneInfo(settings.timezone))} · "
                f"{escape(item['batch'])}\n{escape(item['message'][:70])}"
            )
        text = "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:help")
async def admin_help(callback: CallbackQuery, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("ፈቃድ የለዎትም።", show_alert=True)
        return
    text = (
        "❔ <b>የአስተዳዳሪ መመሪያ</b>\n\n"
        "• አጠቃላይ እይታ — የአባላትና የዓመት ስታቲስቲክስ\n"
        "• አባላት — በየዓመቱ ያሉ አባላት ብዛት\n"
        "• አዲስ ማስታወቂያ — በደረጃ የሚመራ ማዘጋጃ\n"
        "• የታቀዱ መልዕክቶች — የመላኪያ መርሐግብር ይመልከቱ\n\n"
        "Commands: /admin, /users, /broadcast, /schedule, "
        "/schedules, /cancel_schedule ID, /menu"
    )
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def begin_broadcast(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("ፈቃድ የለዎትም።", show_alert=True)
        return
    await state.set_state(AdminBroadcast.choosing_target)
    await callback.message.edit_text(
        "📣 <b>አዲስ ማስታወቂያ</b>\n\n"
        "ደረጃ 1/2 — መልዕክቱ የሚደርሰውን ቡድን ይምረጡ።",
        reply_markup=target_keyboard(settings),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:target:"))
async def choose_broadcast_target(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("ፈቃድ የለዎትም።", show_alert=True)
        return
    if await state.get_state() != AdminBroadcast.choosing_target.state:
        await callback.answer("የማስታወቂያ ሂደቱ ጊዜ አልፎበታል። እባክዎ እንደገና ይጀምሩ።", show_alert=True)
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
        label = display_batch(target)
    await state.update_data(target=target, target_label=label)
    await state.set_state(AdminBroadcast.entering_message)
    await callback.message.edit_text(
        f"📣 <b>አዲስ ማስታወቂያ</b>\nተቀባዮች: <b>{escape(label)}</b>\n\n"
        "ደረጃ 2/2 — የማስታወቂያውን ጽሑፍ በሚቀጥለው መልዕክት ይላኩ።\n"
        "እስከ 4,096 ፊደላት መላክ ይችላሉ። ለማቋረጥ /cancel ይጠቀሙ።"
    )
    await callback.answer()


@router.message(AdminBroadcast.entering_message, F.text & ~F.text.startswith("/"))
async def compose_broadcast(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 4096:
        await message.answer("እባክዎ ከ1 እስከ 4,096 ፊደላት ያሉትን መልዕክት ይላኩ።")
        return
    data = await state.get_data()
    await state.update_data(message=text)
    await state.set_state(AdminBroadcast.confirming)
    await message.answer(
        "🔎 <b>ማስታወቂያውን ይገምግሙ</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"ተቀባዮች: <b>{escape(data.get('target_label', 'ያልታወቀ'))}</b>\n\n"
        f"{escape(text)}\n\n"
        "ይህን ማስታወቂያ አሁን መላክ ይፈልጋሉ?",
        reply_markup=confirmation_keyboard(),
    )


@router.callback_query(F.data == "broadcast:edit")
async def edit_broadcast(callback: CallbackQuery, state: FSMContext, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("ፈቃድ የለዎትም።", show_alert=True)
        return
    if await state.get_state() != AdminBroadcast.confirming.state:
        await callback.answer("የማስታወቂያ ሂደቱ ጊዜ አልፎበታል።", show_alert=True)
        return
    await state.set_state(AdminBroadcast.entering_message)
    await callback.message.edit_text("✏️ የተስተካከለውን የማስታወቂያ ጽሑፍ ይላኩ። ለማቋረጥ /cancel ይጠቀሙ።")
    await callback.answer()


@router.callback_query(F.data == "broadcast:confirm")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, store: JsonStore, settings: Settings):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("ፈቃድ የለዎትም።", show_alert=True)
        return
    if await state.get_state() != AdminBroadcast.confirming.state:
        await callback.answer("የማስታወቂያ ሂደቱ ጊዜ አልፎበታል።", show_alert=True)
        return
    data = await state.get_data()
    target, text = data.get("target"), data.get("message")
    if not target or not text or not valid_target(target, settings):
        await state.clear()
        await callback.answer("የማስታወቂያው መረጃ ያልተሟላ ነው። እባክዎ እንደገና ይጀምሩ።", show_alert=True)
        return
    await callback.message.edit_text("⏳ <b>ማስታወቂያው በመላክ ላይ ነው…</b>")
    sent, failed, total = await send_to_target(callback.message, store, target, text, settings)
    await state.clear()
    await callback.message.edit_text(
        "📬 <b>የመላኪያ ሪፖርት</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"ተቀባዮች: <b>{escape(data.get('target_label', target))}</b>\n"
        f"ተቀባዮች: <b>{total}</b>\n"
        f"የደረሳቸው: <b>{sent}</b>\n"
        f"ያልደረሳቸው: <b>{failed}</b>",
        reply_markup=admin_menu(),
    )
    await callback.answer("የማስታወቂያ ሂደቱ ተጠናቋል።")


@router.callback_query(F.data == "broadcast:cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext, settings: Settings, store: JsonStore):
    if not is_admin(settings, callback.from_user.id):
        await callback.answer("ፈቃድ የለዎትም።", show_alert=True)
        return
    await state.clear()
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    await callback.message.edit_text(
        f"🛡 <b>የአስተዳዳሪ ማዕከል</b>\nየተመዘገቡ አባላት: <b>{len(users)}</b>",
        reply_markup=admin_menu(),
    )
    await callback.answer("ማስታወቂያው ተሰርዟል።")


@router.callback_query(F.data == "member:profile")
async def member_profile(callback: CallbackQuery, store: JsonStore):
    user = await store.get_user(callback.from_user.id)
    if not user:
        await callback.answer("እባክዎ መጀመሪያ /start በመጠቀም ይመዝገቡ።", show_alert=True)
        return
    await callback.message.answer(
        f"👤 <b>የእርስዎ የአባልነት መረጃ</b>\n\n"
        f"ስም: {escape(user['name'])}\nየትምህርት ዓመት: {escape(user['batch'])}"
    )
    await callback.answer()


@router.callback_query(F.data == "member:batch")
async def member_change_batch(callback: CallbackQuery, state: FSMContext, store: JsonStore, settings: Settings):
    user = await store.get_user(callback.from_user.id)
    if not user:
        await callback.answer("እባክዎ መጀመሪያ /start በመጠቀም ይመዝገቡ።", show_alert=True)
        return
    await state.update_data(name=user["name"])
    await state.set_state(Registration.choosing_batch)
    await callback.message.answer("🎓 አዲሱን የትምህርት ዓመት ይምረጡ:", reply_markup=batch_keyboard(settings.batches))
    await callback.answer()


@router.callback_query(F.data == "member:help")
async def member_help(callback: CallbackQuery):
    await callback.message.answer(
        "ℹ️ <b>የአጠቃቀም እገዛ</b>\n\n"
        "/start — ዋና ገጽዎን ይክፈቱ\n"
        "/profile — የአባልነት መረጃዎን ይመልከቱ\n"
        "/edit_batch — የትምህርት ዓመትዎን ይቀይሩ\n"
        "/menu — ዋና ምናሌውን ያሳዩ\n"
        "/cancel — አሁን ያለውን ሂደት ያቋርጡ"
    )
    await callback.answer()


@router.message(Registration.entering_name, F.text & ~F.text.startswith("/"))
async def collect_name(message: Message, state: FSMContext, settings: Settings):
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 80:
        await message.answer("እባክዎ ከ2 እስከ 80 ፊደላት ያሉትን ስም ያስገቡ።")
        return
    await state.update_data(name=name)
    await state.set_state(Registration.choosing_batch)
    await message.answer("🎓 የትምህርት ዓመትዎን ይምረጡ:", reply_markup=batch_keyboard(settings.batches))


@router.message(Registration.choosing_batch, F.text & ~F.text.startswith("/"))
async def collect_batch(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    batch = (message.text or "").strip()
    if batch not in settings.batches:
        await message.answer("እባክዎ ከታች ባለው ምናሌ የትምህርት ዓመትዎን ይምረጡ።", reply_markup=batch_keyboard(settings.batches))
        return
    data = await state.get_data()
    name = data.get("name")
    if not name:
        await state.clear()
        await message.answer("የምዝገባ ሂደቱ ጊዜ አልፎበታል። እባክዎ /start በመጠቀም እንደገና ይጀምሩ።")
        return
    await store.save_user(message.from_user.id, name, batch)
    await state.clear()
    await message.answer(
        "✅ <b>ምዝገባዎ ተጠናቋል</b>\n\n"
        f"ስም: <b>{escape(name)}</b>\nየትምህርት ዓመት: <b>{escape(batch)}</b>\n\n"
        "ከአሁን በኋላ ለትምህርት ዓመትዎ የሚላኩ ማስታወቂያዎችን ያገኛሉ።",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("የአባልነት ምናሌዎ:", reply_markup=member_menu())


@router.message(Command("profile"))
@router.message(Command("my_batch"))
async def profile(message: Message, store: JsonStore):
    user = await store.get_user(message.from_user.id)
    if not user:
        await message.answer("ገና አልተመዘገቡም። /start ይጠቀሙ።")
        return
    await message.answer(f"👤 <b>{escape(user['name'])}</b>\n🎓 {escape(user['batch'])}")


@router.message(Command("edit_batch"))
async def edit_batch(message: Message, state: FSMContext, store: JsonStore, settings: Settings):
    user = await store.get_user(message.from_user.id)
    if not user:
        await message.answer("እባክዎ መጀመሪያ /start ይጠቀሙ።")
        return
    await state.update_data(name=user["name"])
    await state.set_state(Registration.choosing_batch)
    await message.answer("🎓 Choose your new batch:", reply_markup=batch_keyboard(settings.batches))


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext, settings: Settings, store: JsonStore):
    await state.clear()
    if admin_only(settings, message):
        await show_admin_home(message, state, store, settings)
    else:
        await message.answer("ሂደቱ ተሰርዟል።", reply_markup=ReplyKeyboardRemove())


@router.message(Command("help"))
async def help_command(message: Message, settings: Settings):
    if admin_only(settings, message):
        await message.answer(
            "🛡 <b>የአስተዳዳሪ ትዕዛዞች</b>\n\n"
            "/admin — የአስተዳዳሪ ማዕከልን ይክፈቱ\n"
            "/users — የአባላት ቁጥር ሪፖርት\n"
            "/broadcast — ማስታወቂያ ለመላክ\n"
            "/schedule YYYY-MM-DD HH:MM | batch | message — Schedule using Ethiopian date (E.C.)\n"
            "/schedules — የታቀዱ መልዕክቶችን ለማየት\n"
            "/cancel_schedule ID — መርሐግብር ለመሰረዝ\n"
            "/menu — ማዕከሉን ይክፈቱ"
        )
    else:
        await message.answer(
            "ℹ️ <b>Member commands</b>\n\n"
            "/start — ዋና ገጽዎን ይክፈቱ\n"
            "/profile — የአባልነት መረጃዎን ይመልከቱ\n"
            "/edit_batch — የትምህርት ዓመትዎን ይቀይሩ\n"
            "/menu — ዋና ምናሌውን ያሳዩ\n"
            "/cancel — አሁን ያለውን ሂደት ያቋርጡ"
        )


@router.message(Command("users"))
async def users_command(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ This command is restricted to administrators.")
        return
    users = [u for u in await store.list_users() if u["telegram_id"] != settings.super_admin_id]
    counts = {batch: 0 for batch in settings.batches}
    for user in users:
        if user.get("batch") in counts:
            counts[user["batch"]] += 1
    lines = ["👥 <b>የአባላት ሪፖርት</b>", "━━━━━━━━━━━━━━━━━━",
             f"ጠቅላላ የተመዘገቡ: <b>{len(users)}</b>", ""]
    lines.extend(f"• {escape(batch)}: <b>{count}</b>" for batch, count in counts.items())
    await message.answer("\n".join(lines), reply_markup=admin_menu())


async def send_to_target(message: Message, store: JsonStore, target: str, text: str, settings: Settings) -> tuple[int, int, int]:
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
        "📣 <b>የማስታወቂያ ማዘጋጃ</b>\n\n"
        "ደረጃ 1/2 — ማስታወቂያውን የሚቀበሉትን ይምረጡ።",
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
            "🗓 <b>ማስታወቂያ የሚላክበትን ጊዜ ያቅዱ</b>\n\n"
            "አጻጻፍ: /schedule YYYY-MM-DD HH:MM | batch | message (በኢትዮጵያ ዘመን)\n"
            "ለሁሉም አባላት ለመላክ 'all' ይጠቀሙ።\n"
            "Example: /schedule 2019-03-13 09:00 | 1st Year | Class starts at 9 AM\n"
            "ወራት: መስከረም፣ ጥቅምት፣ ኅዳር፣ ታኅሣሥ፣ ጥር፣ የካቲት፣ መጋቢት፣ ሚያዝያ፣ ግንቦት፣ ሰኔ፣ ሐምሌ፣ ነሐሴ፣ ጳጉሜ።"
        )
        return
    time_text, target, text = parts
    if not valid_target(target, settings) or not text or len(text) > 4096:
        await message.answer("የተመረጠው ተቀባይ ወይም መልዕክት ትክክል አይደለም። መልዕክቱ ከ1 እስከ 4,096 ፊደላት መሆን አለበት።")
        return
    try:
        scheduled_at = parse_ethiopian_datetime(time_text, ZoneInfo(settings.timezone))
    except (ValueError, ZoneInfoNotFoundError):
        await message.answer("የኢትዮጵያ ቀን/ሰዓት ወይም የሰዓት ክልሉ ትክክል አይደለም። YYYY-MM-DD HH:MM (ዓ.ም.) ቅርጸት ይጠቀሙ።")
        return
    if scheduled_at <= datetime.now(scheduled_at.tzinfo):
        await message.answer("የታቀደው ጊዜ ከአሁኑ በኋላ መሆን አለበት።")
        return
    item = await store.create_schedule(
        batch=target, message=text, send_at=scheduled_at, created_by=message.from_user.id
    )
    await message.answer(
        "✅ <b>ማስታወቂያው በመርሐግብር ተይዟል</b>\n\n"
        f"መለያ ቁጥር: <b>#{item['id']}</b>\nተቀባዮች: <b>{escape(target)}</b>\n"
        f"የሚላክበት ጊዜ: <b>{format_ethiopian(scheduled_at, ZoneInfo(settings.timezone))}</b>"
    )


@router.message(Command("schedules"))
async def list_schedules(message: Message, store: JsonStore, settings: Settings):
    if not admin_only(settings, message):
        await message.answer("⛔ This command is restricted to administrators.")
        return
    schedules = await store.list_schedules()
    if not schedules:
        await message.answer("🗓 <b>የታቀዱ ማስታወቂያዎች</b>\n\nለመላክ የሚጠብቅ ማስታወቂያ የለም።")
        return
    lines = ["🗓 <b>ለመላክ የሚጠብቁ ማስታወቂያዎች</b>", "━━━━━━━━━━━━━━━━━━"]
    for item in schedules[:30]:
        when = datetime.fromisoformat(item["send_at"]).astimezone(ZoneInfo(settings.timezone))
        lines.append(
            f"#{item['id']} · {format_ethiopian(when, ZoneInfo(settings.timezone))} · {escape(item['batch'])}\n"
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
        await message.answer("አጠቃቀም: /cancel_schedule ID")
        return
    if await store.cancel_schedule(schedule_id):
        await message.answer(f"✅ Scheduled announcement #{schedule_id} cancelled.")
    else:
        await message.answer("በዚህ መለያ ቁጥር የተያዘ ማስታወቂያ አልተገኘም።")
