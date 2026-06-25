"""
Управление заявками (Admin) — просмотр, одобрение, отклонение.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    admin_requests_keyboard,
    request_action_keyboard,
    reject_request_keyboard,
    request_history_nav_keyboard,
    admin_back_keyboard,
)
from bot.states.forms import RejectRequest
from bot.utils.formatters import format_request_for_owner, format_request_history_item, format_datetime
from bot.utils.logger import log_admin_action

router = Router()
PAGE_SIZE = 5


def _is_owner(callback: CallbackQuery) -> bool:
    return callback.from_user.id == config.owner_id


@router.callback_query(F.data == "admin_requests")
async def admin_requests_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    await callback.message.edit_text(
        "📨 <b>Управление заявками</b>\n\nВыберите раздел:",
        reply_markup=admin_requests_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Активные (ожидающие) заявки
# ──────────────────────────────────────────────

@router.callback_query(F.data == "pending_requests")
async def show_pending_requests(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    pending = await queries.get_pending_requests()

    if not pending:
        await callback.message.edit_text(
            "📨 <b>Активные заявки</b>\n\n✅ Нет ожидающих заявок.",
            reply_markup=admin_requests_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Показываем первую заявку
    req = pending[0]
    user_data = {
        "nickname": req["nickname"],
        "telegram_id": req["user_telegram_id"],
        "username": req.get("username")
    }
    text = (
        f"📨 <b>Активные заявки ({len(pending)} шт.)</b>\n\n"
        + format_request_for_owner(req, user_data)
    )

    await callback.message.edit_text(
        text,
        reply_markup=request_action_keyboard(req["id"]),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Одобрение заявки
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("approve_req:"))
async def approve_request(callback: CallbackQuery, bot: Bot) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    req = await queries.get_request_by_id(request_id)

    if not req:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return

    if req["status"] != "pending":
        await callback.answer("⚠️ Заявка уже обработана.", show_alert=True)
        return

    # Обновляем статус заявки
    await queries.update_request_status(request_id, "approved", callback.from_user.id)

    # Начисляем валюту
    user = await queries.get_user_by_id(req["user_id"])
    await queries.update_user_balance(user["id"], req["currency_type"], "add", req["amount"])
    await queries.increment_approved_requests(user["id"])

    # Записываем транзакцию
    await queries.add_transaction(
        user_id=user["id"],
        currency_type=req["currency_type"],
        operation="add",
        amount=req["amount"],
        reason=f"Одобренная заявка #{request_id}: {req['reason']}",
        performed_by=callback.from_user.id
    )

    updated = await queries.get_user_by_id(user["id"])
    is_ticket = req["currency_type"].startswith("tickets_")
    if is_ticket:
        key = req["currency_type"].replace("tickets_", "")
        from bot.utils.formatters import TICKET_NAMES
        emoji, name = TICKET_NAMES.get(key, ("🎫", "Тикет"))
        label = f"{name} тикет"
        balance = f"<b>{int(updated[req['currency_type']])}</b> шт."
        change_text = f"{emoji} +{int(req['amount'])} {label}"
    else:
        emoji = "⭐"
        label = "баллов"
        balance = f"<b>{updated['points']:g}</b>"
        change_text = f"{emoji} +{req['amount']:g} {label}"

    log_admin_action(
        callback.from_user.id,
        "APPROVE_REQUEST",
        f"#{request_id} | {user['nickname']} | {change_text}"
    )

    # Редактируем сообщение у Owner
    await callback.message.edit_text(
        f"✅ <b>Заявка #{request_id} одобрена</b>\n\n"
        f"👤 {user['nickname']}\n"
        f"{change_text}\n"
        f"📊 Новый баланс: {balance}",
        reply_markup=admin_requests_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("✅ Заявка одобрена!")

    # Уведомляем пользователя
    try:
        notif = (
            f"✅ <b>Ваша заявка одобрена!</b>\n\n"
            f"Начислено:\n"
            f"<b>{change_text}</b>\n"
            f"📊 Новый баланс: {balance}"
        )
        await bot.send_message(user["telegram_id"], notif, parse_mode="HTML")
    except Exception:
        pass

    # Если есть ещё ожидающие — показываем следующую
    remaining = await queries.get_pending_requests()
    if remaining:
        next_req = remaining[0]
        user_data = {
            "nickname": next_req["nickname"],
            "telegram_id": next_req["user_telegram_id"],
            "username": next_req.get("username")
        }
        text = (
            f"📨 <b>Следующая заявка ({len(remaining)} осталось)</b>\n\n"
            + format_request_for_owner(next_req, user_data)
        )
        await bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=request_action_keyboard(next_req["id"]),
            parse_mode="HTML"
        )


# ──────────────────────────────────────────────
# Отклонение заявки — выбор способа
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("reject_req:"))
async def reject_request_choose(callback: CallbackQuery) -> None:
    """Промежуточный экран: без причины / с причиной."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    req = await queries.get_request_by_id(request_id)

    if not req:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return

    if req["status"] != "pending":
        await callback.answer("⚠️ Заявка уже обработана.", show_alert=True)
        return

    await callback.message.edit_text(
        f"❌ <b>Отклонение заявки #{request_id}</b>\n\n"
        f"Выберите вариант:",
        reply_markup=reject_request_keyboard(request_id),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Отклонение без причины
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("reject_req_no_reason:"))
async def reject_request_no_reason(callback: CallbackQuery, bot: Bot) -> None:
    """Отклонить заявку без указания причины."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    await _do_reject_request(callback, bot, request_id, reason=None)


# ──────────────────────────────────────────────
# Отклонение с причиной — запрос текста
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("reject_req_with_reason:"))
async def reject_request_ask_reason(callback: CallbackQuery, state: FSMContext) -> None:
    """Запросить ввод причины отклонения."""
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    request_id = int(callback.data.split(":")[1])
    req = await queries.get_request_by_id(request_id)

    if not req:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return

    if req["status"] != "pending":
        await callback.answer("⚠️ Заявка уже обработана.", show_alert=True)
        return

    await state.set_state(RejectRequest.waiting_reason)
    await state.update_data(reject_request_id=request_id)

    from bot.keyboards.admin import cancel_admin_keyboard
    await callback.message.edit_text(
        f"❌ <b>Отклонение заявки #{request_id}</b>\n\n"
        f"📝 Введите причину отклонения:",
        reply_markup=cancel_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Отклонение с причиной — обработка текста
# ──────────────────────────────────────────────

@router.message(RejectRequest.waiting_reason)
async def reject_request_reason_entered(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработать введённую причину и отклонить заявку."""
    if message.from_user.id != config.owner_id:
        return

    if not message.text:
        from bot.keyboards.admin import cancel_admin_keyboard
        await message.answer(
            "⚠️ Пожалуйста, введите текстовую причину отклонения.",
            reply_markup=cancel_admin_keyboard()
        )
        return

    reason = message.text.strip()
    if len(reason) < 2:
        from bot.keyboards.admin import cancel_admin_keyboard
        await message.answer(
            "⚠️ Причина слишком короткая. Минимум 2 символа.",
            reply_markup=cancel_admin_keyboard()
        )
        return

    data = await state.get_data()
    request_id = data.get("reject_request_id")
    await state.clear()

    if not request_id:
        await message.answer("❌ Сессия устарела. Попробуйте заново.")
        return

    # Используем FakeCallback для совместимости с _do_reject_request
    class _FakeCallback:
        def __init__(self, msg):
            self.message = msg
            self.from_user = msg.from_user
        async def answer(self, *a, **kw):
            pass

    await _do_reject_request(_FakeCallback(message), bot, request_id, reason=reason)


# ──────────────────────────────────────────────
# Общая логика отклонения заявки
# ──────────────────────────────────────────────

async def _do_reject_request(callback, bot: Bot, request_id: int, reason: str | None) -> None:
    """Отклонить заявку и уведомить пользователя."""
    req = await queries.get_request_by_id(request_id)

    if not req:
        await callback.answer("❌ Заявка не найдена.", show_alert=True)
        return

    if req["status"] != "pending":
        await callback.answer("⚠️ Заявка уже обработана.", show_alert=True)
        return

    await queries.update_request_status(request_id, "rejected", callback.from_user.id)

    user = await queries.get_user_by_id(req["user_id"])
    is_ticket = req["currency_type"].startswith("tickets_")
    if is_ticket:
        key = req["currency_type"].replace("tickets_", "")
        from bot.utils.formatters import TICKET_NAMES
        emoji, name = TICKET_NAMES.get(key, ("🎫", "Тикет"))
        label = f"{name} тикет"
        amount_str = f"{int(req['amount'])}"
    else:
        emoji = "⭐"
        label = "баллов"
        amount_str = f"{req['amount']:g}"

    reason_log = f" | Причина: {reason}" if reason else ""
    log_admin_action(
        callback.from_user.id,
        "REJECT_REQUEST",
        f"#{request_id} | {user['nickname']} | {emoji} {amount_str} {label}{reason_log}"
    )

    reason_line = f"\n📝 Причина: {reason}" if reason else ""
    text = (
        f"❌ <b>Заявка #{request_id} отклонена</b>\n\n"
        f"👤 {user['nickname']}\n"
        f"{emoji} {amount_str} {label}{reason_line}"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=admin_requests_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=admin_requests_keyboard(),
            parse_mode="HTML"
        )

    if hasattr(callback, "answer"):
        try:
            await callback.answer("❌ Заявка отклонена.")
        except Exception:
            pass


    # Уведомляем пользователя
    try:
        reason_user = f"\n\n📝 Причина: {reason}" if reason else ""
        await bot.send_message(
            user["telegram_id"],
            f"❌ <b>Ваша заявка была отклонена.</b>{reason_user}",
            parse_mode="HTML"
        )
    except Exception:
        pass

    # Следующая заявка
    remaining = await queries.get_pending_requests()
    if remaining:
        next_req = remaining[0]
        user_data = {
            "nickname": next_req["nickname"],
            "telegram_id": next_req["user_telegram_id"],
            "username": next_req.get("username")
        }
        text = (
            f"📨 <b>Следующая заявка ({len(remaining)} осталось)</b>\n\n"
            + format_request_for_owner(next_req, user_data)
        )
        await bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=request_action_keyboard(next_req["id"]),
            parse_mode="HTML"
        )


# ──────────────────────────────────────────────
# История заявок
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("requests_history:"))
async def show_requests_history(callback: CallbackQuery) -> None:
    if not _is_owner(callback):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return

    offset = int(callback.data.split(":")[1])
    requests = await queries.get_requests_history(limit=PAGE_SIZE, offset=offset)
    total = await queries.count_requests_history()

    if not requests:
        await callback.message.edit_text(
            "📋 <b>История заявок</b>\n\nИстория пуста.",
            reply_markup=request_history_nav_keyboard(offset, total, PAGE_SIZE),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    lines = [f"📋 <b>История заявок</b> (стр. {offset // PAGE_SIZE + 1})\n"]
    for req in requests:
        lines.append(f"\n{format_request_history_item(req)}")
        lines.append("─" * 30)

    text = "\n".join(lines).rstrip("─").rstrip()

    await callback.message.edit_text(
        text,
        reply_markup=request_history_nav_keyboard(offset, total, PAGE_SIZE),
        parse_mode="HTML"
    )
    await callback.answer()
