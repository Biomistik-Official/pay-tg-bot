"""Быстрые команды для личных чатов и групп."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import config
from bot.database import queries
from bot.handlers.profile import build_profile_text
from bot.handlers.start import show_main_menu
from bot.keyboards.treasury import treasury_list_keyboard
from bot.keyboards.user import (
    back_to_main_keyboard,
    points_menu_keyboard,
    shop_main_keyboard,
    tickets_menu_keyboard,
)

router = Router()


async def _get_user(message: Message) -> dict | None:
    user = await queries.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Снача зарегистрируйся у бота в личке через /start.")
        return None
    return user


@router.message(Command("vgsmenu", "menu"))
async def command_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await _get_user(message)
    if user:
        await show_main_menu(message, user)


@router.message(Command("profile"))
async def command_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await _get_user(message)
    if not user:
        return
    await message.answer(
        await build_profile_text(user),
        reply_markup=back_to_main_keyboard(),
    )


@router.message(Command("tickets", "tickests"))
async def command_tickets(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await _get_user(message)
    if not user:
        return
    tickets = [
        ("💎", "Платиновые", user.get("tickets_platinum", 0)),
        ("🥇", "Золотые", user.get("tickets_gold", 0)),
        ("🥈", "Серебряные", user.get("tickets_silver", 0)),
        ("🥉", "Бронзовые", user.get("tickets_bronze", 0)),
        ("🎁", "Вспомогательные", user.get("tickets_support", 0)),
        ("💪", "Хелп", user.get("tickets_help", 0)),
    ]
    lines = ["🎫 <b>Тикеты</b>", ""]
    lines.extend(f"{emoji} {name}: <b>{amount}</b> шт." for emoji, name, amount in tickets)
    lines.extend(["", "Выбери действие:"])
    await message.answer("\n".join(lines), reply_markup=tickets_menu_keyboard())


@router.message(Command("points"))
async def command_points(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await _get_user(message)
    if not user:
        return
    await message.answer(
        f"⭐ <b>Баллы</b>\n\nУ тебя: <b>{user['points']:g}</b>",
        reply_markup=points_menu_keyboard(),
    )


@router.message(Command("stars"))
async def command_stars(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await _get_user(message)
    if not user:
        return
    await message.answer(
        f"🌟 <b>Звёзды</b>\n\nУ тебя: <b>{int(user.get('stars', 0) or 0)}</b> шт.",
        reply_markup=back_to_main_keyboard(),
    )


@router.message(Command("shop"))
async def command_shop(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await _get_user(message)
    if not user:
        return
    await message.answer(
        "🛒 <b>Магазин VGS Money</b>\n\nВыбери раздел:",
        reply_markup=shop_main_keyboard(),
    )


@router.message(Command("kazna", "treasury"))
async def command_treasury(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await _get_user(message)
    if not user:
        return
    treasuries = await queries.get_treasuries()
    lines = ["🏦 <b>Казны клана</b>", ""]
    lines.extend(
        f"{item['emoji']} {item['name']} — <b>{item['points_balance']:g} ⭐</b>"
        for item in treasuries
    )
    await message.answer(
        "\n".join(lines),
        reply_markup=treasury_list_keyboard(
            treasuries,
            user["telegram_id"] == config.owner_id,
        ),
    )
