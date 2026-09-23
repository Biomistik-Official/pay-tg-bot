"""Казны клана: пополнения, распределение, участники и выдачи Staff."""

import html
import secrets
from decimal import Decimal, ROUND_DOWN
from math import isfinite

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import config
from bot.database import queries
from bot.keyboards.treasury import (
    confirm_keyboard,
    currency_keyboard,
    distribution_mode_keyboard,
    history_keyboard,
    member_actions_keyboard,
    members_keyboard,
    payout_member_keyboard,
    payout_mode_keyboard,
    percentages_keyboard,
    simple_cancel_keyboard,
    split_mode_keyboard,
    topup_mode_keyboard,
    treasury_list_keyboard,
    treasury_multi_pick_keyboard,
    treasury_page_keyboard,
    treasury_pick_keyboard,
)
from bot.states.forms import (
    TreasuryDistribution,
    TreasuryDonation,
    TreasuryMemberAdd,
    TreasuryPayout,
    TreasuryPercentages,
    TreasurySpend,
    TreasuryTopUp,
)
from bot.utils.formatters import format_datetime
from bot.utils.logger import log_admin_action
from bot.utils.treasury import TREASURY_CURRENCIES, format_treasury_amount

router = Router()
PAGE_SIZE = 8


def _is_owner(telegram_id: int) -> bool:
    return telegram_id == config.owner_id


def _parse_amount(raw: str, currency_type: str) -> float | int:
    value = float(raw.strip().replace(" ", "").replace(",", "."))
    if not isfinite(value) or value <= 0:
        raise ValueError
    if TREASURY_CURRENCIES[currency_type]["integer"]:
        if not value.is_integer():
            raise ValueError
        return int(value)
    return round(value, 2)


def _split_amount(total: float, weights: list[Decimal], integer: bool) -> list[float | int]:
    scale = Decimal("1") if integer else Decimal("0.01")
    total_decimal = Decimal(str(total)).quantize(scale)
    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError("Сумма процентов равна нулю")
    raw = [total_decimal * weight / weight_sum for weight in weights]
    result = [value.quantize(scale, rounding=ROUND_DOWN) for value in raw]
    remainder_units = int((total_decimal - sum(result)) / scale)
    order = sorted(range(len(raw)), key=lambda index: raw[index] - result[index], reverse=True)
    for index in order[:remainder_units]:
        result[index] += scale
    if integer:
        return [int(value) for value in result]
    return [float(value) for value in result]


def _treasury_title(item: dict) -> str:
    return f"{item['emoji']} {item['name']}"


async def _show_treasury_list(callback: CallbackQuery, state: FSMContext | None = None) -> None:
    if state:
        await state.clear()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        return await callback.answer("Профиль не найден. Введи /start", show_alert=True)
    treasuries = await queries.get_treasuries()
    lines = ["🏦 <b>Казны клана</b>", ""]
    for item in treasuries:
        lines.append(f"{_treasury_title(item)} — <b>{item['points_balance']:g} ⭐</b>")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=treasury_list_keyboard(treasuries, _is_owner(callback.from_user.id)),
    )
    await callback.answer()


@router.callback_query(F.data == "treasury")
async def show_treasury_list(callback: CallbackQuery, state: FSMContext) -> None:
    await _show_treasury_list(callback, state)


@router.callback_query(F.data == "treasury_cancel")
async def cancel_treasury(callback: CallbackQuery, state: FSMContext) -> None:
    await _show_treasury_list(callback, state)


@router.callback_query(F.data.startswith("treasury_view:"))
async def show_treasury(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    treasury_id = int(callback.data.split(":")[1])
    item = await queries.get_treasury(treasury_id)
    if not item:
        return await callback.answer("Казна не найдена.", show_alert=True)
    balances = await queries.get_treasury_balances(treasury_id)
    lines = [
        f"{item['emoji']} <b>{html.escape(item['name'])}</b>",
        "",
        f"⭐ Баланс: <b>{item['points_balance']:g}</b>",
        f"👥 Участников: <b>{item['members_count']}</b>",
        f"📅 Последнее пополнение: <b>{format_datetime(item['last_deposit']) if item['last_deposit'] else '—'}</b>",
    ]
    other = [
        format_treasury_amount(currency, amount)
        for currency, amount in balances.items()
        if currency != "points" and amount
    ]
    if other:
        lines.extend(["", "💳 <b>Другие средства:</b>", *other])
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=treasury_page_keyboard(treasury_id, _is_owner(callback.from_user.id), bool(item["is_general"])),
    )
    await callback.answer()


# Пополнение казен

@router.callback_query(F.data == "treasury_topup")
async def start_topup(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "➕ <b>Пополнение казны</b>\n\nВыбери режим:",
        reply_markup=topup_mode_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_topup_one:"))
async def start_topup_from_page(callback: CallbackQuery, state: FSMContext) -> None:
    treasury_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.update_data(selected_ids=[treasury_id], split_mode="single")
    await callback.message.edit_text(
        "💳 <b>Выбери валюту пополнения:</b>",
        reply_markup=currency_keyboard("treasury_topup_currency"),
    )
    await callback.answer()


@router.callback_query(F.data == "treasury_topup_single")
async def choose_single_treasury(callback: CallbackQuery, state: FSMContext) -> None:
    treasuries = await queries.get_treasuries()
    await state.update_data(split_mode="single")
    await callback.message.edit_text(
        "🏦 <b>Какую казну пополнить?</b>",
        reply_markup=treasury_pick_keyboard(treasuries, "treasury_topup_pick"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_topup_pick:"))
async def single_treasury_picked(callback: CallbackQuery, state: FSMContext) -> None:
    treasury_id = int(callback.data.split(":")[1])
    await state.update_data(selected_ids=[treasury_id])
    await callback.message.edit_text(
        "💳 <b>Выбери валюту пополнения:</b>",
        reply_markup=currency_keyboard("treasury_topup_currency"),
    )
    await callback.answer()


@router.callback_query(F.data == "treasury_topup_selected")
async def choose_multiple_treasuries(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(selected_ids=[])
    treasuries = await queries.get_treasuries()
    await callback.message.edit_text(
        "🏦 <b>Отметь нужные казны:</b>",
        reply_markup=treasury_multi_pick_keyboard(treasuries, set()),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_topup_toggle:"))
async def toggle_topup_treasury(callback: CallbackQuery, state: FSMContext) -> None:
    treasury_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("selected_ids", []))
    selected.symmetric_difference_update({treasury_id})
    await state.update_data(selected_ids=list(selected))
    treasuries = await queries.get_treasuries()
    await callback.message.edit_reply_markup(reply_markup=treasury_multi_pick_keyboard(treasuries, selected))
    await callback.answer()


@router.callback_query(F.data == "treasury_topup_all")
async def topup_all_treasuries(callback: CallbackQuery, state: FSMContext) -> None:
    treasuries = await queries.get_treasuries()
    await state.update_data(selected_ids=[item["id"] for item in treasuries])
    await callback.message.edit_text(
        "⚖️ <b>Как распределить сумму между всеми казнами?</b>",
        reply_markup=split_mode_keyboard(allow_percent=False),
    )
    await callback.answer()


@router.callback_query(F.data == "treasury_topup_selection_done")
async def finish_treasury_selection(callback: CallbackQuery, state: FSMContext) -> None:
    selected = set((await state.get_data()).get("selected_ids", []))
    if not selected:
        return await callback.answer("Выбери хотя бы одну казну.", show_alert=True)
    if len(selected) == 1:
        await state.update_data(split_mode="single")
        await callback.message.edit_text(
            "💳 <b>Выбери валюту пополнения:</b>",
            reply_markup=currency_keyboard("treasury_topup_currency"),
        )
        return await callback.answer()
    treasuries = await queries.get_treasuries()
    general_ids = {item["id"] for item in treasuries if item["is_general"]}
    await callback.message.edit_text(
        "⚖️ <b>Как распределить сумму?</b>",
        reply_markup=split_mode_keyboard(allow_percent=not bool(selected & general_ids)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_split:"))
async def choose_split_mode(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":")[1]
    await state.update_data(split_mode=mode)
    await callback.message.edit_text(
        "💳 <b>Выбери валюту пополнения:</b>",
        reply_markup=currency_keyboard("treasury_topup_currency"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_topup_currency:"))
async def choose_topup_currency(callback: CallbackQuery, state: FSMContext) -> None:
    currency_type = callback.data.split(":")[1]
    if currency_type not in TREASURY_CURRENCIES:
        return await callback.answer("Неизвестная валюта.", show_alert=True)
    data = await state.get_data()
    selected_ids = data.get("selected_ids", [])
    if not selected_ids:
        return await callback.answer("Казны не выбраны.", show_alert=True)
    await state.update_data(currency_type=currency_type)
    if data.get("split_mode") == "manual" and len(selected_ids) > 1:
        treasuries = {item["id"]: item for item in await queries.get_treasuries()}
        await state.update_data(manual_index=0, manual_amounts={})
        await state.set_state(TreasuryTopUp.waiting_manual_amount)
        current = treasuries[selected_ids[0]]
        text = f"✍️ Введи сумму для {_treasury_title(current)}:"
    else:
        await state.set_state(TreasuryTopUp.waiting_amount)
        text = "✍️ Введи общую сумму пополнения:"
    await callback.message.edit_text(text, reply_markup=simple_cancel_keyboard())
    await callback.answer()


@router.message(TreasuryTopUp.waiting_manual_amount)
async def enter_manual_topup_amount(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        amount = _parse_amount(message.text or "", data["currency_type"])
    except (ValueError, OverflowError):
        return await message.answer("⚠️ Введи положительное число.", reply_markup=simple_cancel_keyboard())
    selected_ids = data["selected_ids"]
    index = data.get("manual_index", 0)
    amounts = dict(data.get("manual_amounts", {}))
    amounts[str(selected_ids[index])] = amount
    index += 1
    await state.update_data(manual_amounts=amounts, manual_index=index)
    if index < len(selected_ids):
        treasuries = {item["id"]: item for item in await queries.get_treasuries()}
        return await message.answer(
            f"✍️ Введи сумму для {_treasury_title(treasuries[selected_ids[index]])}:",
            reply_markup=simple_cancel_keyboard(),
        )
    await state.update_data(amounts={int(key): value for key, value in amounts.items()})
    await state.set_state(TreasuryTopUp.waiting_reason)
    await message.answer("📝 Введи причину или комментарий:", reply_markup=simple_cancel_keyboard())


@router.message(TreasuryTopUp.waiting_amount)
async def enter_topup_amount(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        total = _parse_amount(message.text or "", data["currency_type"])
    except (ValueError, OverflowError):
        return await message.answer("⚠️ Введи положительное число.", reply_markup=simple_cancel_keyboard())
    selected_ids = data["selected_ids"]
    mode = data.get("split_mode", "single")
    if mode == "percent":
        settings = {item["treasury_id"]: Decimal(str(item["percentage"])) for item in await queries.get_distribution_settings()}
        weights = [settings.get(treasury_id, Decimal("0")) for treasury_id in selected_ids]
    else:
        weights = [Decimal("1")] * len(selected_ids)
    try:
        shares = _split_amount(total, weights, TREASURY_CURRENCIES[data["currency_type"]]["integer"])
    except ValueError as error:
        return await message.answer(f"❌ {error}", reply_markup=simple_cancel_keyboard())
    amounts = {treasury_id: share for treasury_id, share in zip(selected_ids, shares) if share > 0}
    if len(amounts) != len(selected_ids):
        return await message.answer(
            "❌ Сумма слишком мала: хотя бы одна казна получает 0.",
            reply_markup=simple_cancel_keyboard(),
        )
    await state.update_data(amounts=amounts)
    await state.set_state(TreasuryTopUp.waiting_reason)
    await message.answer("📝 Введи причину или комментарий:", reply_markup=simple_cancel_keyboard())


@router.message(TreasuryTopUp.waiting_reason)
async def enter_topup_reason(message: Message, state: FSMContext) -> None:
    reason = (message.text or "").strip()
    if not reason:
        return await message.answer("Причина не может быть пустой.")
    data = await state.get_data()
    await state.update_data(reason=reason, request_key=secrets.token_hex(16))
    await state.set_state(TreasuryTopUp.confirm)
    treasuries = {item["id"]: item for item in await queries.get_treasuries()}
    lines = ["➕ <b>Пополнение казен</b>", ""]
    for treasury_id, amount in data["amounts"].items():
        lines.append(f"{_treasury_title(treasuries[int(treasury_id)])} → {format_treasury_amount(data['currency_type'], amount)}")
    lines.extend(["", f"Итого: <b>{format_treasury_amount(data['currency_type'], sum(data['amounts'].values()))}</b>", f"📝 {html.escape(reason)}"])
    await message.answer("\n".join(lines), reply_markup=confirm_keyboard("treasury_topup_confirm"))


@router.callback_query(F.data == "treasury_topup_confirm", TreasuryTopUp.confirm)
async def confirm_topup(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        return await callback.answer("Профиль не найден.", show_alert=True)
    try:
        await queries.top_up_treasuries(
            {int(key): value for key, value in data["amounts"].items()},
            data["currency_type"], callback.from_user.id, user["id"],
            data["reason"], "owner_topup" if _is_owner(callback.from_user.id) else "user_topup",
            data["request_key"],
        )
    except ValueError as error:
        return await callback.answer(f"❌ {error}", show_alert=True)
    await state.clear()
    await callback.message.edit_text("✅ Казны пополнены. Все операции записаны в историю.")
    await callback.answer()


# Пожертвование с личного баланса

@router.callback_query(F.data == "treasury_donate")
async def start_donation(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    treasuries = await queries.get_treasuries()
    await callback.message.edit_text(
        "❤️ <b>Пожертвование</b>\n\nВыбери казну:",
        reply_markup=treasury_pick_keyboard(treasuries, "treasury_donate_pick"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_donate_pick:"))
async def choose_donation_treasury(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(treasury_id=int(callback.data.split(":")[1]))
    await callback.message.edit_text(
        "💳 <b>Что пожертвовать?</b>",
        reply_markup=currency_keyboard("treasury_donate_currency", donation_only=True),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_donate_currency:"))
async def choose_donation_currency(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(currency_type=callback.data.split(":")[1])
    await state.set_state(TreasuryDonation.waiting_amount)
    await callback.message.edit_text("✍️ Введи сумму пожертвования:", reply_markup=simple_cancel_keyboard())
    await callback.answer()


@router.message(TreasuryDonation.waiting_amount)
async def enter_donation_amount(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        amount = _parse_amount(message.text or "", data["currency_type"])
    except (ValueError, OverflowError):
        return await message.answer("⚠️ Введи положительное число.")
    await state.update_data(amount=amount)
    await state.set_state(TreasuryDonation.waiting_reason)
    await message.answer("📝 Введи комментарий:", reply_markup=simple_cancel_keyboard())


@router.message(TreasuryDonation.waiting_reason)
async def enter_donation_reason(message: Message, state: FSMContext) -> None:
    reason = (message.text or "").strip()
    data = await state.get_data()
    treasury = await queries.get_treasury(data["treasury_id"])
    await state.update_data(reason=reason, request_key=secrets.token_hex(16))
    await state.set_state(TreasuryDonation.confirm)
    await message.answer(
        f"❤️ <b>Пожертвование</b>\n\n"
        f"🏦 {_treasury_title(treasury)}\n"
        f"Сумма: <b>{format_treasury_amount(data['currency_type'], data['amount'])}</b>\n"
        f"📝 {html.escape(reason) or 'без комментария'}",
        reply_markup=confirm_keyboard("treasury_donate_confirm", "✅ Пожертвовать"),
    )


@router.callback_query(F.data == "treasury_donate_confirm", TreasuryDonation.confirm)
async def confirm_donation(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user = await queries.get_user_by_telegram_id(callback.from_user.id)
    try:
        await queries.donate_to_treasury(
            data["treasury_id"], user["id"], data["currency_type"], data["amount"],
            callback.from_user.id, data["reason"], data["request_key"],
        )
    except queries.TreasuryInsufficientFundsError:
        return await callback.answer("❌ Недостаточно средств на личном балансе.", show_alert=True)
    except ValueError as error:
        return await callback.answer(f"❌ {error}", show_alert=True)
    await state.clear()
    await callback.message.edit_text("✅ Пожертвование зачислено. Спасибо!")
    await callback.answer()


# Списание Owner

@router.callback_query(F.data.startswith("treasury_spend:"))
async def start_spend(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    treasury_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.update_data(treasury_id=treasury_id)
    await callback.message.edit_text(
        "➖ <b>Списание из казны</b>\n\nВыбери валюту:",
        reply_markup=currency_keyboard("treasury_spend_currency"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_spend_currency:"))
async def choose_spend_currency(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.update_data(currency_type=callback.data.split(":")[1])
    await state.set_state(TreasurySpend.waiting_amount)
    await callback.message.edit_text("✍️ Введи сумму списания:", reply_markup=simple_cancel_keyboard())
    await callback.answer()


@router.message(TreasurySpend.waiting_amount)
async def enter_spend_amount(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    try:
        amount = _parse_amount(message.text or "", data["currency_type"])
    except (ValueError, OverflowError):
        return await message.answer("⚠️ Введи положительное число.")
    await state.update_data(amount=amount)
    await state.set_state(TreasurySpend.waiting_reason)
    await message.answer("📝 Введи причину списания:", reply_markup=simple_cancel_keyboard())


@router.message(TreasurySpend.waiting_reason)
async def enter_spend_reason(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    reason = (message.text or "").strip()
    if not reason:
        return await message.answer("Причина не может быть пустой.")
    data = await state.get_data()
    treasury = await queries.get_treasury(data["treasury_id"])
    await state.update_data(reason=reason, request_key=secrets.token_hex(16))
    await state.set_state(TreasurySpend.confirm)
    await message.answer(
        f"➖ <b>Списание</b>\n\n🏦 {_treasury_title(treasury)}\n"
        f"Сумма: <b>{format_treasury_amount(data['currency_type'], data['amount'])}</b>\n"
        f"📝 {html.escape(reason)}",
        reply_markup=confirm_keyboard("treasury_spend_confirm"),
    )


@router.callback_query(F.data == "treasury_spend_confirm", TreasurySpend.confirm)
async def confirm_spend(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    data = await state.get_data()
    try:
        await queries.spend_from_treasury(
            data["treasury_id"], data["currency_type"], data["amount"],
            callback.from_user.id, data["reason"], data["request_key"],
        )
    except queries.TreasuryInsufficientFundsError:
        return await callback.answer("❌ Недостаточно средств в казне.", show_alert=True)
    log_admin_action(callback.from_user.id, "Списание из казны", f"treasury={data['treasury_id']} amount={data['amount']} {data['currency_type']}")
    await state.clear()
    await callback.message.edit_text("✅ Средства списаны.")
    await callback.answer()


# Распределение общей казны и проценты

async def _distribution_preview(amount: float, state: FSMContext) -> tuple[str, dict[int, float]]:
    settings = await queries.get_distribution_settings()
    shares = _split_amount(amount, [Decimal(str(item["percentage"])) for item in settings], False)
    allocations = {item["treasury_id"]: share for item, share in zip(settings, shares) if share > 0}
    lines = ["📊 <b>Распределение</b>", "", f"🌐 Распределяется: <b>{amount:g} ⭐</b>", ""]
    for item, share in zip(settings, shares):
        lines.append(f"{item['emoji']} {item['name']} → <b>{share:g} ⭐</b> ({item['percentage']:g}%)")
    lines.extend(["", f"Итого: <b>{sum(shares):g} ⭐</b>"])
    await state.update_data(amount=amount, allocations=allocations, request_key=secrets.token_hex(16))
    await state.set_state(TreasuryDistribution.confirm)
    return "\n".join(lines), allocations


@router.callback_query(F.data == "treasury_distribute")
async def start_distribution(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.clear()
    general = await queries.get_treasury_by_code("general")
    balances = await queries.get_treasury_balances(general["id"])
    await callback.message.edit_text(
        f"📊 <b>Распределение общей казны</b>\n\nТекущий баланс:\n⭐ <b>{balances.get('points', 0):g} баллов</b>",
        reply_markup=distribution_mode_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "treasury_dist_all")
async def distribute_all_preview(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    general = await queries.get_treasury_by_code("general")
    balance = (await queries.get_treasury_balances(general["id"])).get("points", 0)
    if balance <= 0:
        return await callback.answer("Общая казна пуста.", show_alert=True)
    text, _ = await _distribution_preview(balance, state)
    await callback.message.edit_text(text, reply_markup=confirm_keyboard("treasury_dist_confirm"))
    await callback.answer()


@router.callback_query(F.data == "treasury_dist_amount")
async def ask_distribution_amount(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(TreasuryDistribution.waiting_amount)
    await callback.message.edit_text("✍️ Введи сумму баллов для распределения:", reply_markup=simple_cancel_keyboard())
    await callback.answer()


@router.message(TreasuryDistribution.waiting_amount)
async def enter_distribution_amount(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    try:
        amount = _parse_amount(message.text or "", "points")
    except (ValueError, OverflowError):
        return await message.answer("⚠️ Введи положительное число.")
    general = await queries.get_treasury_by_code("general")
    balance = (await queries.get_treasury_balances(general["id"])).get("points", 0)
    if amount > balance:
        return await message.answer("❌ Недостаточно средств в общей казне.")
    text, _ = await _distribution_preview(amount, state)
    await message.answer(text, reply_markup=confirm_keyboard("treasury_dist_confirm"))


@router.callback_query(F.data == "treasury_dist_confirm", TreasuryDistribution.confirm)
async def confirm_distribution(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    data = await state.get_data()
    try:
        await queries.distribute_general_treasury(
            data["amount"], {int(key): value for key, value in data["allocations"].items()},
            callback.from_user.id, "Распределение общей казны", data["request_key"],
        )
    except queries.TreasuryInsufficientFundsError:
        return await callback.answer("❌ Недостаточно средств в общей казне.", show_alert=True)
    except ValueError as error:
        return await callback.answer(f"❌ {error}", show_alert=True)
    log_admin_action(callback.from_user.id, "Распределение казны", f"amount={data['amount']}")
    await state.clear()
    await callback.message.edit_text("✅ Баланс общей казны распределён.")
    await callback.answer()


@router.callback_query(F.data == "treasury_percentages")
async def show_percentages(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.clear()
    settings = await queries.get_distribution_settings()
    lines = ["⚙️ <b>Проценты казны</b>", ""]
    lines.extend(f"{item['emoji']} {item['name']} — <b>{item['percentage']:g}%</b>" for item in settings)
    lines.extend(["", f"Итого: <b>{sum(item['percentage'] for item in settings):g}%</b>"])
    await callback.message.edit_text("\n".join(lines), reply_markup=percentages_keyboard())
    await callback.answer()


@router.callback_query(F.data == "treasury_percentages_edit")
async def edit_percentages(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    settings = await queries.get_distribution_settings()
    await state.update_data(percentage_ids=[item["treasury_id"] for item in settings])
    await state.set_state(TreasuryPercentages.waiting_values)
    names = "\n".join(f"{index}. {item['emoji']} {item['name']}" for index, item in enumerate(settings, 1))
    await callback.message.edit_text(
        f"✏️ <b>Новые проценты</b>\n\n{names}\n\n"
        "Введи проценты одной строкой через пробел в этом порядке.\n"
        "Пример: <code>25 15 15 10 10 10 15</code>",
        reply_markup=simple_cancel_keyboard(),
    )
    await callback.answer()


@router.message(TreasuryPercentages.waiting_values)
async def save_percentages(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    try:
        values = [float(part.replace(",", ".")) for part in (message.text or "").split()]
    except ValueError:
        return await message.answer("❌ Введи только числа через пробел.")
    if len(values) != len(data["percentage_ids"]):
        return await message.answer(f"❌ Нужно указать {len(data['percentage_ids'])} значений.")
    try:
        await queries.set_distribution_settings(dict(zip(data["percentage_ids"], values)), message.from_user.id)
    except ValueError as error:
        return await message.answer(f"❌ Ошибка. {error}")
    log_admin_action(message.from_user.id, "Изменение процентов казны", str(values))
    await state.clear()
    await message.answer("✅ Проценты сохранены. Сумма: 100%.")


# Участники казны

@router.callback_query(F.data.startswith("treasury_members:"))
async def show_members(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    treasury_id = int(callback.data.split(":")[1])
    treasury = await queries.get_treasury(treasury_id)
    members = await queries.get_treasury_members(treasury_id)
    await callback.message.edit_text(
        f"👥 <b>Участники — {html.escape(treasury['name'])}</b>\n\nВсего: <b>{len(members)}</b>",
        reply_markup=members_keyboard(treasury_id, members),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_member:"))
async def show_member_actions(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    _, treasury_id, user_id = callback.data.split(":")
    user = await queries.get_user_by_id(int(user_id))
    activity = await queries.get_staff_activity(int(user_id))
    await callback.message.edit_text(
        f"🛠 <b>{html.escape(user['nickname'])}</b>\n\n"
        f"📊 Активности Staff: <b>{activity['activity_count']}</b>\n"
        f"⭐ Баллы: <b>{user['points']:g}</b>",
        reply_markup=member_actions_keyboard(int(treasury_id), int(user_id), user["telegram_id"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_member_add:"))
async def start_add_member(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    treasury_id = int(callback.data.split(":")[1])
    await state.set_state(TreasuryMemberAdd.waiting_search)
    await state.update_data(treasury_id=treasury_id)
    await callback.message.edit_text("➕ Введи никнейм или Telegram ID Staff:", reply_markup=simple_cancel_keyboard())
    await callback.answer()


@router.message(TreasuryMemberAdd.waiting_search)
async def add_member(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    search = (message.text or "").strip()
    user = await queries.get_user_by_telegram_id(int(search)) if search.lstrip("-").isdigit() else None
    if not user:
        user = await queries.get_user_by_nickname(search)
    if not user or not await queries.get_staff_by_user_id(user["id"]):
        return await message.answer("❌ Активный Staff не найден.")
    treasury_id = (await state.get_data())["treasury_id"]
    await queries.assign_staff_to_treasury(treasury_id, user["id"], message.from_user.id)
    await state.clear()
    log_admin_action(message.from_user.id, "Назначение Staff в казну", f"user={user['telegram_id']} treasury={treasury_id}")
    await message.answer(f"✅ <b>{html.escape(user['nickname'])}</b> назначен в казну.")


@router.callback_query(F.data.startswith("treasury_member_remove:"))
async def remove_member(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    _, treasury_id, user_id = callback.data.split(":")
    await queries.remove_staff_from_treasury(int(treasury_id), int(user_id))
    log_admin_action(callback.from_user.id, "Удаление Staff из казны", f"user={user_id} treasury={treasury_id}")
    await callback.answer("✅ Staff удалён из казны.", show_alert=True)
    members = await queries.get_treasury_members(int(treasury_id))
    await callback.message.edit_text("👥 <b>Участники казны</b>", reply_markup=members_keyboard(int(treasury_id), members))


@router.callback_query(F.data.startswith("treasury_member_move:"))
async def choose_member_target(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    _, current_id, user_id = callback.data.split(":")
    treasuries = [
        item for item in await queries.get_treasuries()
        if item["id"] != int(current_id) and not item["is_general"]
    ]
    await state.update_data(move_user_id=int(user_id))
    await callback.message.edit_text(
        "🔄 <b>Выбери новую казну:</b>",
        reply_markup=treasury_pick_keyboard(treasuries, "treasury_member_target"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_member_target:"))
async def move_member(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    treasury_id = int(callback.data.split(":")[1])
    user_id = (await state.get_data()).get("move_user_id")
    if not user_id:
        return await callback.answer("Сессия устарела.", show_alert=True)
    await queries.assign_staff_to_treasury(treasury_id, user_id, callback.from_user.id)
    await state.clear()
    log_admin_action(callback.from_user.id, "Перевод Staff между казнами", f"user={user_id} treasury={treasury_id}")
    await callback.message.edit_text("✅ Staff переведён в другую казну.")
    await callback.answer()


# Выдача Staff

@router.callback_query(F.data.startswith("treasury_payout:"))
async def payout_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    treasury_id = int(callback.data.split(":")[1])
    treasury = await queries.get_treasury(treasury_id)
    await callback.message.edit_text(
        f"💰 <b>Выдать баллы — {html.escape(treasury['name'])}</b>",
        reply_markup=payout_mode_keyboard(treasury_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_payout_group:"))
async def payout_group_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    treasury_id = int(callback.data.split(":")[1])
    members = await queries.get_treasury_members(treasury_id)
    if not members:
        return await callback.answer("В казне нет Staff.", show_alert=True)
    await state.update_data(treasury_id=treasury_id, payout_user_id=None)
    await state.set_state(TreasuryPayout.waiting_amount)
    await callback.message.edit_text("✍️ Введи сумму баллов для каждого Staff:", reply_markup=simple_cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_payout_one:"))
async def choose_payout_member(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    treasury_id = int(callback.data.split(":")[1])
    members = await queries.get_treasury_members(treasury_id)
    if not members:
        return await callback.answer("В казне нет Staff.", show_alert=True)
    await callback.message.edit_text(
        "👤 <b>Выбери получателя:</b>",
        reply_markup=payout_member_keyboard(treasury_id, members),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("treasury_payout_user:"))
async def payout_user_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    _, treasury_id, user_id = callback.data.split(":")
    user = await queries.get_user_by_id(int(user_id))
    activity = await queries.get_staff_activity(int(user_id))
    await state.update_data(treasury_id=int(treasury_id), payout_user_id=int(user_id))
    await state.set_state(TreasuryPayout.waiting_amount)
    await callback.message.edit_text(
        f"👤 <b>{html.escape(user['nickname'])}</b>\n"
        f"🛠 Роль: Staff\n"
        f"📊 Активности Staff: {activity['activity_count']}\n\n"
        "✍️ Введи сумму баллов:",
        reply_markup=simple_cancel_keyboard(),
    )
    await callback.answer()


@router.message(TreasuryPayout.waiting_amount)
async def payout_amount_entered(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    try:
        amount = _parse_amount(message.text or "", "points")
    except (ValueError, OverflowError):
        return await message.answer("⚠️ Введи положительное число.")
    data = await state.get_data()
    members = await queries.get_treasury_members(data["treasury_id"])
    if data.get("payout_user_id"):
        members = [member for member in members if member["user_id"] == data["payout_user_id"]]
    payouts = {member["user_id"]: amount for member in members}
    total = amount * len(members)
    treasury = await queries.get_treasury(data["treasury_id"])
    if total > treasury["points_balance"]:
        return await message.answer("❌ Недостаточно средств в казне. Никому ничего не начислено.")
    await state.update_data(payouts=payouts, request_key=secrets.token_hex(16))
    await state.set_state(TreasuryPayout.confirm)
    lines = [f"👥 <b>Выдача из казны «{html.escape(treasury['name'])}»</b>", ""]
    lines.extend(f"🛠 {html.escape(member['nickname'])} — <b>{amount:g} ⭐</b>" for member in members)
    lines.extend(["", f"Всего будет списано: <b>{total:g} ⭐</b>"])
    await message.answer("\n".join(lines), reply_markup=confirm_keyboard("treasury_payout_confirm", "✅ Выдать"))


@router.callback_query(F.data == "treasury_payout_confirm", TreasuryPayout.confirm)
async def confirm_payout(callback: CallbackQuery, state: FSMContext, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    data = await state.get_data()
    try:
        await queries.payout_staff_from_treasury(
            data["treasury_id"], {int(key): value for key, value in data["payouts"].items()},
            callback.from_user.id, "Выдача Staff из казны", data["request_key"],
        )
    except queries.TreasuryInsufficientFundsError:
        return await callback.answer("❌ Недостаточно средств в казне. Никому ничего не начислено.", show_alert=True)
    except ValueError as error:
        return await callback.answer(f"❌ {error}", show_alert=True)
    for user_id, amount in data["payouts"].items():
        user = await queries.get_user_by_id(int(user_id))
        try:
            await bot.send_message(user["telegram_id"], f"💰 Тебе выдано <b>{amount:g} ⭐</b> из казны.")
        except Exception:
            pass
    log_admin_action(callback.from_user.id, "Выдача Staff из казны", f"treasury={data['treasury_id']} recipients={len(data['payouts'])}")
    await state.clear()
    await callback.message.edit_text("✅ Баллы выданы, операции записаны в историю.")
    await callback.answer()


# История

@router.callback_query(F.data.startswith("treasury_history:"))
async def show_history(callback: CallbackQuery) -> None:
    _, treasury_id, offset = callback.data.split(":")
    treasury_id, offset = int(treasury_id), int(offset)
    treasury = await queries.get_treasury(treasury_id)
    rows = await queries.get_treasury_history(treasury_id, PAGE_SIZE, offset)
    total = await queries.count_treasury_history(treasury_id)
    operation_names = {
        "donation": "❤️ Пожертвование",
        "manual_deposit": "➕ Пополнение",
        "expense": "➖ Списание",
        "distribution_out": "📤 Распределение",
        "distribution_in": "📥 Получено из общей казны",
        "staff_payout": "💰 Выдача Staff",
    }
    lines = [f"📜 <b>История — {html.escape(treasury['name'])}</b>"]
    if not rows:
        lines.extend(["", "Операций пока нет."])
    for row in rows:
        actor = html.escape(row.get("actor_nickname") or str(row["initiated_by_telegram_id"]))
        details = []
        if row.get("related_treasury_name"):
            details.append(f"🏦 {row['related_treasury_emoji']} {html.escape(row['related_treasury_name'])}")
        if row.get("related_user_nickname"):
            details.append(f"👤 {html.escape(row['related_user_nickname'])}")
        details.append(f"💰 {format_treasury_amount(row['currency_type'], row['amount'])}")
        details.append(f"💳 {row['balance_before']:g} → {row['balance_after']:g}")
        details.append(f"👑 {actor}")
        if row.get("reason"):
            details.append(f"📝 {html.escape(row['reason'])}")
        details.append(f"📅 {format_datetime(row['created_at'])}")
        lines.extend(["", f"<b>{operation_names.get(row['operation_type'], row['operation_type'])}</b>", *details])
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=history_keyboard(treasury_id, offset, total, PAGE_SIZE),
    )
    await callback.answer()
