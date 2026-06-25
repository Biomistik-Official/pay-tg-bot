"""
Управление заявками (Admin) — просмотр, одобрение, отклонение.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import (
    admin_requests_keyboard,
    request_action_keyboard,
    request_history_nav_keyboard,
    admin_back_keyboard,
)
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
# Отклонение заявки
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("reject_req:"))
async def reject_request(callback: CallbackQuery, bot: Bot) -> None:
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

    log_admin_action(
        callback.from_user.id,
        "REJECT_REQUEST",
        f"#{request_id} | {user['nickname']} | {emoji} {amount_str} {label}"
    )

    await callback.message.edit_text(
        f"❌ <b>Заявка #{request_id} отклонена</b>\n\n"
        f"👤 {user['nickname']}\n"
        f"{emoji} {amount_str} {label}",
        reply_markup=admin_requests_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("❌ Заявка отклонена.")

    # Уведомляем пользователя
    try:
        await bot.send_message(
            user["telegram_id"],
            "❌ <b>Ваша заявка была отклонена.</b>",
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
