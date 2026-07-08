"""
Категории Staff (Owner only).

Позволяет распределять Staff по подразделениям, выдавать зарплату/штрафы,
делать рассылки, вести историю операций.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database import queries
from bot.keyboards.admin import cancel_admin_keyboard
from bot.keyboards.categories import (
    categories_menu_keyboard, category_detail_keyboard,
    category_edit_field_keyboard, category_delete_confirm_keyboard,
    category_members_keyboard, category_member_actions_keyboard,
    category_add_member_keyboard, category_move_keyboard,
    category_salary_confirm_keyboard, category_salary_one_pick_keyboard,
    category_penalty_scope_keyboard, category_penalty_pick_member_keyboard,
    category_penalty_confirm_keyboard, category_broadcast_confirm_keyboard,
    category_history_keyboard, category_coefs_keyboard,
)
from bot.states.forms import (
    CategoryCreate, CategoryEdit,
    CategorySalary, CategorySalarySingle, CategoryPenalty,
    CategoryBroadcast, CategoryCoefEdit,
)
from bot.utils.ranks import rank_label, rank_name, DEFAULT_RANK
from bot.utils.logger import log_admin_action
from bot.utils.formatters import format_datetime

router = Router()


def _is_owner(uid: int) -> bool:
    return uid == config.owner_id


def _round_points(v: float) -> float:
    return round(v, 2)


# Главное меню категорий

@router.callback_query(F.data == "admin_cats")
async def show_categories_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await state.clear()
    cats = await queries.get_all_staff_categories()
    if not cats:
        text = (
            "📂 <b>Категории Staff</b>\n\n"
            "Пока нет ни одной категории. Создайте первую."
        )
    else:
        lines = ["📂 <b>Категории Staff</b>\n"]
        for c in cats:
            lines.append(
                f"{c['name']} — ×{c['coefficient']:g} · "
                f"{c['members_count']} чел."
            )
        text = "\n".join(lines)
    await callback.message.edit_text(
        text, reply_markup=categories_menu_keyboard(cats), parse_mode="HTML"
    )
    await callback.answer()


# Просмотр категории

@router.callback_query(F.data.startswith("cat_view:"))
async def show_category(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await state.clear()
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    members = await queries.get_category_members(category_id)
    comment = cat.get("comment") or "—"
    text = (
        f"📂 <b>{cat['name']}</b>\n\n"
        f"📝 Описание: {cat.get('description') or '—'}\n"
        f"📈 Коэффициент: <b>×{cat['coefficient']:g}</b>\n"
        f"💬 Комментарий: {comment}\n\n"
        f"👥 Участников: <b>{len(members)}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=category_detail_keyboard(category_id), parse_mode="HTML"
    )
    await callback.answer()


# Создание категории

@router.callback_query(F.data == "cat_create")
async def start_create_category(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await state.set_state(CategoryCreate.waiting_name)
    await callback.message.edit_text(
        "📂 <b>Новая категория</b>\n\n"
        "Введите <b>название</b> категории (например: <i>🎯 Активности</i>):",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.message(CategoryCreate.waiting_name)
async def create_name(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    name = message.text.strip()
    if not name or len(name) > 60:
        return await message.answer(
            "⚠️ Название должно быть от 1 до 60 символов.",
            reply_markup=cancel_admin_keyboard(),
        )
    await state.update_data(name=name)
    await state.set_state(CategoryCreate.waiting_description)
    await message.answer(
        "Теперь введите <b>описание</b> категории.\n"
        "Отправьте <code>-</code>, чтобы оставить пустым.",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )


@router.message(CategoryCreate.waiting_description)
async def create_desc(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    desc = message.text.strip()
    if desc == "-":
        desc = ""
    await state.update_data(description=desc)
    await state.set_state(CategoryCreate.waiting_coefficient)
    await message.answer(
        "Введите <b>коэффициент</b> категории (например, <code>10</code> — итог будет ×10).",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )


@router.message(CategoryCreate.waiting_coefficient)
async def create_coef(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    try:
        coef = float(message.text.strip().replace(",", "."))
        if coef <= 0:
            raise ValueError
    except ValueError:
        return await message.answer(
            "⚠️ Введите положительное число.",
            reply_markup=cancel_admin_keyboard(),
        )
    await state.update_data(coefficient=coef)
    await state.set_state(CategoryCreate.waiting_comment)
    await message.answer(
        "Введите <b>комментарий</b> (необязательно).\n"
        "Отправьте <code>-</code>, чтобы пропустить.",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )


@router.message(CategoryCreate.waiting_comment)
async def create_finish(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    comment = message.text.strip()
    if comment == "-":
        comment = ""
    data = await state.get_data()
    cat_id = await queries.create_staff_category(
        name=data["name"],
        description=data.get("description", ""),
        coefficient=data["coefficient"],
        comment=comment,
    )
    await state.clear()
    log_admin_action(
        message.from_user.id,
        "Создание категории Staff",
        f"id={cat_id} name={data['name']} coef={data['coefficient']:g}",
    )
    cats = await queries.get_all_staff_categories()
    await message.answer(
        f"✅ Категория <b>{data['name']}</b> создана.",
        reply_markup=categories_menu_keyboard(cats), parse_mode="HTML",
    )


# Редактирование

@router.callback_query(F.data.startswith("cat_edit:"))
async def edit_category_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    await callback.message.edit_text(
        f"✏️ <b>Редактирование категории</b>\n\n"
        f"📌 {cat['name']}\n"
        f"📝 {cat.get('description') or '—'}\n"
        f"📈 ×{cat['coefficient']:g}\n"
        f"💬 {cat.get('comment') or '—'}\n\n"
        f"Выберите поле:",
        reply_markup=category_edit_field_keyboard(category_id), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_edit_field:"))
async def edit_category_field(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, cat_str, field = callback.data.split(":")
    category_id = int(cat_str)
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    labels = {
        "name":        "название",
        "description": "описание",
        "coefficient": "коэффициент (число)",
        "comment":     "комментарий",
    }
    await state.set_state(CategoryEdit.waiting_value)
    await state.update_data(category_id=category_id, field=field)
    await callback.message.edit_text(
        f"✏️ Введите новое <b>{labels[field]}</b> для категории <b>{cat['name']}</b>:",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.message(CategoryEdit.waiting_value)
async def edit_category_apply(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    category_id = data["category_id"]
    field = data["field"]
    raw = message.text.strip()

    if field == "coefficient":
        try:
            value = float(raw.replace(",", "."))
            if value <= 0:
                raise ValueError
        except ValueError:
            return await message.answer(
                "⚠️ Введите положительное число.",
                reply_markup=cancel_admin_keyboard(),
            )
    elif field == "name":
        if not raw or len(raw) > 60:
            return await message.answer(
                "⚠️ Название должно быть от 1 до 60 символов.",
                reply_markup=cancel_admin_keyboard(),
            )
        value = raw
    else:
        value = "" if raw == "-" else raw

    await queries.update_staff_category(category_id, **{field: value})
    await state.clear()
    log_admin_action(
        message.from_user.id,
        "Изменение категории Staff",
        f"id={category_id} {field}={value!r}",
    )
    cat = await queries.get_staff_category(category_id)
    await message.answer(
        f"✅ Категория обновлена.\n\n"
        f"📌 {cat['name']}\n"
        f"📝 {cat.get('description') or '—'}\n"
        f"📈 ×{cat['coefficient']:g}\n"
        f"💬 {cat.get('comment') or '—'}",
        reply_markup=category_detail_keyboard(category_id), parse_mode="HTML",
    )


# Удаление

@router.callback_query(F.data.startswith("cat_delete:"))
async def delete_category_ask(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    members = await queries.get_category_members(category_id)
    await callback.message.edit_text(
        f"⚠️ Удалить категорию <b>{cat['name']}</b>?\n\n"
        f"В категории {len(members)} чел. — они останутся Staff, "
        f"но будут откреплены от категории.\n"
        f"История начислений будет обезличена.",
        reply_markup=category_delete_confirm_keyboard(category_id), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_delete_confirm:"))
async def delete_category_do(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    await queries.delete_staff_category(category_id)
    log_admin_action(
        callback.from_user.id,
        "Удаление категории Staff",
        f"id={category_id} name={cat['name']}",
    )
    cats = await queries.get_all_staff_categories()
    await callback.message.edit_text(
        f"🗑 Категория <b>{cat['name']}</b> удалена.",
        reply_markup=categories_menu_keyboard(cats), parse_mode="HTML",
    )
    await callback.answer()


# Участники

@router.callback_query(F.data.startswith("cat_members:"))
async def show_members(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await state.clear()
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    members = await queries.get_category_members(category_id)
    if not members:
        text = f"👥 <b>{cat['name']} — участники</b>\n\nПока никого нет."
    else:
        lines = [f"👥 <b>{cat['name']} — участники ({len(members)})</b>\n"]
        for m in members:
            r = m.get("rank") or DEFAULT_RANK
            lines.append(f"• {rank_label(r)} <b>{m['nickname']}</b>")
        text = "\n".join(lines)
    await callback.message.edit_text(
        text, reply_markup=category_members_keyboard(category_id, members),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_member:"))
async def view_member(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, cat_str, tg_str = callback.data.split(":")
    category_id = int(cat_str)
    telegram_id = int(tg_str)
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    rank = await queries.get_staff_rank(user["id"])
    quest_coef = await queries.get_rank_coefficient(rank)
    cat_coef = await queries.get_rank_category_coefficient(rank)
    cat = await queries.get_staff_category(category_id)
    text = (
        f"👤 <b>{user['nickname']}</b>\n"
        f"@{user.get('username') or '—'} | <code>{telegram_id}</code>\n\n"
        f"🎖 Ранг: {rank_label(rank)}\n"
        f"📋 Квест-коэф.: <b>×{quest_coef:g}</b>\n"
        f"📂 Кат.-коэф.: <b>×{cat_coef:g}</b>\n"
        f"📂 Категория: <b>{cat['name']}</b> (×{cat['coefficient']:g})"
    )
    await callback.message.edit_text(
        text,
        reply_markup=category_member_actions_keyboard(category_id, telegram_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_kick:"))
async def kick_member(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, cat_str, tg_str = callback.data.split(":")
    category_id = int(cat_str)
    telegram_id = int(tg_str)
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    await queries.set_staff_category(user["id"], None)
    log_admin_action(
        callback.from_user.id,
        "Удаление из категории",
        f"user={user['nickname']} ({telegram_id}) category={category_id}",
    )
    await callback.answer(f"✅ {user['nickname']} удалён из категории.", show_alert=True)
    # Обновить список
    members = await queries.get_category_members(category_id)
    cat = await queries.get_staff_category(category_id)
    if not members:
        text = f"👥 <b>{cat['name']} — участники</b>\n\nПока никого нет."
    else:
        lines = [f"👥 <b>{cat['name']} — участники ({len(members)})</b>\n"]
        for m in members:
            r = m.get("rank") or DEFAULT_RANK
            lines.append(f"• {rank_label(r)} <b>{m['nickname']}</b>")
        text = "\n".join(lines)
    await callback.message.edit_text(
        text, reply_markup=category_members_keyboard(category_id, members),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cat_move:"))
async def move_member(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, cat_str, tg_str = callback.data.split(":")
    telegram_id = int(tg_str)
    current_cat_id = int(cat_str)
    all_cats = await queries.get_all_staff_categories()
    targets = [c for c in all_cats if c["id"] != current_cat_id]
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    if not targets:
        return await callback.answer(
            "Других категорий нет.", show_alert=True
        )
    await callback.message.edit_text(
        f"🔄 <b>Куда перевести {user['nickname']}?</b>",
        reply_markup=category_move_keyboard(targets, telegram_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_move_to:"))
async def move_to(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, new_cat_str, tg_str = callback.data.split(":")
    new_cat_id = int(new_cat_str)
    telegram_id = int(tg_str)
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    new_cat_id_val = new_cat_id if new_cat_id != 0 else None
    await queries.set_staff_category(user["id"], new_cat_id_val)
    log_admin_action(
        callback.from_user.id,
        "Перевод Staff в категорию",
        f"user={user['nickname']} ({telegram_id}) → category_id={new_cat_id_val}",
    )
    if new_cat_id_val is None:
        await callback.answer("✅ Убран из категории.", show_alert=True)
        cats = await queries.get_all_staff_categories()
        await callback.message.edit_text(
            "📂 <b>Категории Staff</b>\n\nВыберите категорию:",
            reply_markup=categories_menu_keyboard(cats), parse_mode="HTML",
        )
    else:
        cat = await queries.get_staff_category(new_cat_id_val)
        await callback.answer(f"✅ Переведён в {cat['name']}.", show_alert=True)
        # Открыть новую категорию
        members = await queries.get_category_members(new_cat_id_val)
        text = (
            f"📂 <b>{cat['name']}</b>\n\n"
            f"📝 {cat.get('description') or '—'}\n"
            f"📈 ×{cat['coefficient']:g}\n\n"
            f"👥 Участников: <b>{len(members)}</b>"
        )
        await callback.message.edit_text(
            text, reply_markup=category_detail_keyboard(new_cat_id_val),
            parse_mode="HTML",
        )


# Добавление участника

@router.callback_query(F.data.startswith("cat_add_member:"))
async def add_member_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    free_staff = await queries.get_staff_without_category()
    if not free_staff:
        return await callback.answer(
            "Все Staff уже в категориях. Переведите нужного через профиль.",
            show_alert=True,
        )
    await callback.message.edit_text(
        f"➕ <b>Добавить в {cat['name']}</b>\n\n"
        f"Выберите Staff (без категории):",
        reply_markup=category_add_member_keyboard(category_id, free_staff),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_add_pick:"))
async def add_member_pick(callback: CallbackQuery, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, cat_str, tg_str = callback.data.split(":")
    category_id = int(cat_str)
    telegram_id = int(tg_str)
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    await queries.set_staff_category(user["id"], category_id)
    log_admin_action(
        callback.from_user.id,
        "Добавление в категорию",
        f"user={user['nickname']} ({telegram_id}) → {cat['name']}",
    )
    try:
        await bot.send_message(
            telegram_id,
            f"📂 Вы добавлены в категорию Staff: <b>{cat['name']}</b>.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer(f"✅ {user['nickname']} добавлен.", show_alert=True)
    # Обновляем список свободных
    free_staff = await queries.get_staff_without_category()
    if not free_staff:
        members = await queries.get_category_members(category_id)
        if not members:
            text = f"👥 <b>{cat['name']} — участники</b>\n\nПока никого нет."
        else:
            lines = [f"👥 <b>{cat['name']} — участники ({len(members)})</b>\n"]
            for m in members:
                r = m.get("rank") or DEFAULT_RANK
                lines.append(f"• {rank_label(r)} <b>{m['nickname']}</b>")
            text = "\n".join(lines)
        await callback.message.edit_text(
            text, reply_markup=category_members_keyboard(category_id, members),
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            f"➕ <b>Добавить в {cat['name']}</b>\n\n"
            f"Выберите Staff (без категории):",
            reply_markup=category_add_member_keyboard(category_id, free_staff),
            parse_mode="HTML",
        )


# Зарплата — всей категории

@router.callback_query(F.data.startswith("cat_salary:"))
async def salary_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    members = await queries.get_category_members(category_id)
    if not members:
        return await callback.answer("В категории нет участников.", show_alert=True)

    n = len(members)
    items = []
    for m in members:
        rank = m.get("rank") or DEFAULT_RANK
        rank_coef = await queries.get_rank_category_coefficient(rank)
        amount = _round_points(cat["coefficient"] * rank_coef / n)
        items.append({
            "user_id": m["user_id"],
            "telegram_id": m["telegram_id"],
            "nickname": m["nickname"],
            "rank": rank,
            "rank_coef": rank_coef,
            "category_coef": cat["coefficient"],
            "amount": amount,
        })

    await state.set_state(CategorySalary.waiting_confirm)
    await state.update_data(category_id=category_id, base=cat["coefficient"], items=items)

    lines = [
        f"💰 <b>Предпросмотр — {cat['name']}</b>\n",
        f"📈 Коэф. категории: <b>×{cat['coefficient']:g}</b> · участников: <b>{n}</b>",
        f"<i>Формула: кат.коэф.ранга × коэф.категории / N</i>\n",
        "👥 Будет начислено:",
    ]
    for it in items:
        lines.append(
            f"• {it['nickname']} — <b>{it['amount']:g}</b> баллов "
            f"({rank_name(it['rank'])} ×{it['rank_coef']:g})"
        )
    total = sum(it["amount"] for it in items)
    lines.append(f"\n🧮 Итого: <b>{total:g}</b> баллов")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=category_salary_confirm_keyboard(category_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(CategorySalary.waiting_confirm, F.data == "cat_salary_confirm")
async def salary_apply(callback: CallbackQuery, state: FSMContext, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    data = await state.get_data()
    category_id = data["category_id"]
    items = data["items"]
    base = data["base"]
    cat = await queries.get_staff_category(category_id)
    if not cat:
        await state.clear()
        return await callback.answer("Категория не найдена.", show_alert=True)

    reason = f"Зарплата: {cat['name']} (база {base:g})"
    for it in items:
        await queries.update_user_balance(
            it["user_id"], "points", "add", it["amount"]
        )
        await queries.add_transaction(
            user_id=it["user_id"],
            currency_type="points",
            operation="add",
            amount=it["amount"],
            reason=reason,
            performed_by=callback.from_user.id,
        )
        try:
            await bot.send_message(
                it["telegram_id"],
                f"💰 <b>Зарплата — {cat['name']}</b>\n\n"
                f"Начислено: <b>{it['amount']:g}</b> баллов\n"
                f"({rank_name(it['rank'])} ×{it['rank_coef']:g} × "
                f"×{cat['coefficient']:g} / {len(items)})",
                parse_mode="HTML",
            )
        except Exception:
            pass

    op_id = await queries.record_category_operation(
        category_id=category_id,
        operation_type="salary",
        scope="category",
        base_amount=base,
        performed_by=callback.from_user.id,
        items=items,
    )
    log_admin_action(
        callback.from_user.id,
        "Зарплата категории",
        f"op={op_id} cat={cat['name']} base={base:g} n={len(items)}",
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ Зарплата начислена: <b>{cat['name']}</b>\n"
        f"База: {base:g}, получателей: {len(items)}.",
        reply_markup=category_detail_keyboard(category_id), parse_mode="HTML",
    )
    await callback.answer()


# Зарплата — одному сотруднику

@router.callback_query(F.data.startswith("cat_salary_one:"))
async def salary_one_menu(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    members = await queries.get_category_members(category_id)
    if not members:
        return await callback.answer("В категории нет участников.", show_alert=True)
    await callback.message.edit_text(
        f"👤 <b>Зарплата сотруднику — {cat['name']}</b>\n\nВыберите:",
        reply_markup=category_salary_one_pick_keyboard(category_id, members),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_salary_one_pick:"))
async def salary_one_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, cat_str, tg_str = callback.data.split(":")
    category_id = int(cat_str)
    telegram_id = int(tg_str)
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    rank = await queries.get_staff_rank(user["id"])
    rank_coef = await queries.get_rank_category_coefficient(rank)
    await state.set_state(CategorySalarySingle.waiting_base)
    await state.update_data(
        category_id=category_id,
        target_user_id=user["id"],
        target_telegram_id=telegram_id,
        target_nickname=user["nickname"],
        target_rank=rank,
        rank_coef=rank_coef,
    )
    await callback.message.edit_text(
        f"👤 <b>Зарплата: {user['nickname']}</b>\n\n"
        f"Категория: {cat['name']} (×{cat['coefficient']:g})\n"
        f"Ранг: {rank_label(rank)} · кат.коэф. <b>×{rank_coef:g}</b>\n\n"
        f"Введите базовую сумму:",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.message(CategorySalarySingle.waiting_base)
async def salary_one_calc(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    try:
        base = float(message.text.strip().replace(",", "."))
        if base <= 0:
            raise ValueError
    except ValueError:
        return await message.answer(
            "⚠️ Введите положительное число.",
            reply_markup=cancel_admin_keyboard(),
        )
    data = await state.get_data()
    cat = await queries.get_staff_category(data["category_id"])
    amount = _round_points(base * cat["coefficient"] * data["rank_coef"])
    await state.update_data(base=base, amount=amount)
    await state.set_state(CategorySalarySingle.waiting_confirm)
    await message.answer(
        f"💰 <b>Предпросмотр</b>\n\n"
        f"👤 {data['target_nickname']}\n"
        f"📈 {base:g} × ×{cat['coefficient']:g} × ×{data['rank_coef']:g} = "
        f"<b>{amount:g}</b> баллов",
        reply_markup=category_salary_confirm_keyboard(data["category_id"]),
        parse_mode="HTML",
    )


@router.callback_query(CategorySalarySingle.waiting_confirm, F.data == "cat_salary_confirm")
async def salary_one_apply(callback: CallbackQuery, state: FSMContext, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    data = await state.get_data()
    category_id = data["category_id"]
    cat = await queries.get_staff_category(category_id)
    if not cat:
        await state.clear()
        return await callback.answer("Категория не найдена.", show_alert=True)

    reason = f"Зарплата: {cat['name']} (база {data['base']:g})"
    await queries.update_user_balance(
        data["target_user_id"], "points", "add", data["amount"]
    )
    await queries.add_transaction(
        user_id=data["target_user_id"],
        currency_type="points",
        operation="add",
        amount=data["amount"],
        reason=reason,
        performed_by=callback.from_user.id,
    )
    try:
        await bot.send_message(
            data["target_telegram_id"],
            f"💰 <b>Зарплата — {cat['name']}</b>\n\n"
            f"Начислено: <b>{data['amount']:g}</b> баллов",
            parse_mode="HTML",
        )
    except Exception:
        pass

    op_id = await queries.record_category_operation(
        category_id=category_id,
        operation_type="salary",
        scope="single",
        base_amount=data["base"],
        performed_by=callback.from_user.id,
        items=[{
            "user_id": data["target_user_id"],
            "amount": data["amount"],
            "rank": data["target_rank"],
            "rank_coef": data["rank_coef"],
            "category_coef": cat["coefficient"],
        }],
    )
    log_admin_action(
        callback.from_user.id,
        "Зарплата сотруднику",
        f"op={op_id} user={data['target_nickname']} amount={data['amount']:g}",
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ Начислено {data['amount']:g} баллов пользователю "
        f"<b>{data['target_nickname']}</b>.",
        reply_markup=category_detail_keyboard(category_id), parse_mode="HTML",
    )
    await callback.answer()


# Штраф

@router.callback_query(F.data.startswith("cat_penalty:"))
async def penalty_scope(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await state.clear()
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    await callback.message.edit_text(
        f"⚠️ <b>Штраф — {cat['name']}</b>\n\nКого штрафуем?",
        reply_markup=category_penalty_scope_keyboard(category_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_penalty_all:"))
async def penalty_all_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    members = await queries.get_category_members(category_id)
    if not members:
        return await callback.answer("В категории нет участников.", show_alert=True)
    await state.set_state(CategoryPenalty.waiting_amount)
    await state.update_data(category_id=category_id, scope="category")
    await callback.message.edit_text(
        f"⚠️ <b>Штраф всей категории ({cat['name']})</b>\n\n"
        f"Сколько баллов списать с каждого?",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_penalty_one:"))
async def penalty_one_pick(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    members = await queries.get_category_members(category_id)
    if not members:
        return await callback.answer("В категории нет участников.", show_alert=True)
    await callback.message.edit_text(
        f"👤 <b>Штраф одному — {cat['name']}</b>\n\nВыберите:",
        reply_markup=category_penalty_pick_member_keyboard(category_id, members),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_penalty_pick:"))
async def penalty_one_amount(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    _, cat_str, tg_str = callback.data.split(":")
    category_id = int(cat_str)
    telegram_id = int(tg_str)
    user = await queries.get_user_by_telegram_id(telegram_id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    await state.set_state(CategoryPenalty.waiting_amount)
    await state.update_data(
        category_id=category_id,
        scope="single",
        target_user_id=user["id"],
        target_telegram_id=telegram_id,
        target_nickname=user["nickname"],
    )
    await callback.message.edit_text(
        f"⚠️ <b>Штраф: {user['nickname']}</b>\n\nВведите количество баллов:",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.message(CategoryPenalty.waiting_amount)
async def penalty_preview(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        return await message.answer(
            "⚠️ Введите положительное число.",
            reply_markup=cancel_admin_keyboard(),
        )
    data = await state.get_data()
    category_id = data["category_id"]
    cat = await queries.get_staff_category(category_id)

    if data["scope"] == "category":
        members = await queries.get_category_members(category_id)
        items = [{
            "user_id":       m["user_id"],
            "telegram_id":   m["telegram_id"],
            "nickname":      m["nickname"],
            "rank":          m.get("rank") or DEFAULT_RANK,
            "rank_coef":     None,
            "category_coef": cat["coefficient"],
            "amount":        _round_points(amount),
        } for m in members]
        lines = [
            f"⚠️ <b>Штраф — {cat['name']}</b>\n",
            f"Со <b>всех</b> будет списано по <b>{amount:g}</b> баллов:\n",
        ]
        for it in items:
            lines.append(f"• {it['nickname']} — <b>-{it['amount']:g}</b>")
        lines.append(f"\n🧮 Итого: <b>{amount*len(items):g}</b> баллов")
    else:
        items = [{
            "user_id":       data["target_user_id"],
            "telegram_id":   data["target_telegram_id"],
            "nickname":      data["target_nickname"],
            "rank":          None,
            "rank_coef":     None,
            "category_coef": cat["coefficient"],
            "amount":        _round_points(amount),
        }]
        lines = [
            f"⚠️ <b>Штраф</b>\n",
            f"👤 {data['target_nickname']} — <b>-{amount:g}</b> баллов",
        ]

    await state.update_data(base=amount, items=items)
    await state.set_state(CategoryPenalty.waiting_confirm)
    await message.answer(
        "\n".join(lines),
        reply_markup=category_penalty_confirm_keyboard(category_id),
        parse_mode="HTML",
    )


@router.callback_query(CategoryPenalty.waiting_confirm, F.data == "cat_penalty_confirm")
async def penalty_apply(callback: CallbackQuery, state: FSMContext, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    data = await state.get_data()
    category_id = data["category_id"]
    cat = await queries.get_staff_category(category_id)
    if not cat:
        await state.clear()
        return await callback.answer("Категория не найдена.", show_alert=True)

    reason = f"Штраф: {cat['name']}"
    for it in data["items"]:
        await queries.update_user_balance(
            it["user_id"], "points", "subtract", it["amount"]
        )
        await queries.add_transaction(
            user_id=it["user_id"],
            currency_type="points",
            operation="subtract",
            amount=it["amount"],
            reason=reason,
            performed_by=callback.from_user.id,
        )
        try:
            await bot.send_message(
                it["telegram_id"],
                f"⚠️ <b>Штраф — {cat['name']}</b>\n\n"
                f"Списано: <b>{it['amount']:g}</b> баллов.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    op_id = await queries.record_category_operation(
        category_id=category_id,
        operation_type="penalty",
        scope=data.get("scope", "category"),
        base_amount=data["base"],
        performed_by=callback.from_user.id,
        items=data["items"],
    )
    log_admin_action(
        callback.from_user.id,
        "Штраф категории",
        f"op={op_id} cat={cat['name']} n={len(data['items'])} amount={data['base']:g}",
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ Штраф применён ({len(data['items'])} чел.).",
        reply_markup=category_detail_keyboard(category_id), parse_mode="HTML",
    )
    await callback.answer()


# Рассылка

@router.callback_query(F.data.startswith("cat_broadcast:"))
async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    members = await queries.get_category_members(category_id)
    if not members:
        return await callback.answer("В категории нет участников.", show_alert=True)
    await state.set_state(CategoryBroadcast.waiting_text)
    await state.update_data(category_id=category_id)
    await callback.message.edit_text(
        f"📢 <b>Сообщение категории — {cat['name']}</b>\n\nВведите текст:",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.message(CategoryBroadcast.waiting_text)
async def broadcast_confirm(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    text = message.text.strip()
    if not text:
        return await message.answer(
            "⚠️ Пустое сообщение.", reply_markup=cancel_admin_keyboard(),
        )
    data = await state.get_data()
    cat = await queries.get_staff_category(data["category_id"])
    await state.update_data(text=text)
    await state.set_state(CategoryBroadcast.waiting_confirm)
    await message.answer(
        f"📢 <b>Отправить всем в {cat['name']}?</b>\n\n<i>{text}</i>",
        reply_markup=category_broadcast_confirm_keyboard(data["category_id"]),
        parse_mode="HTML",
    )


@router.callback_query(CategoryBroadcast.waiting_confirm, F.data == "cat_broadcast_confirm")
async def broadcast_send(callback: CallbackQuery, state: FSMContext, bot) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    data = await state.get_data()
    category_id = data["category_id"]
    text = data["text"]
    cat = await queries.get_staff_category(category_id)
    members = await queries.get_category_members(category_id)
    sent = 0
    for m in members:
        try:
            await bot.send_message(
                m["telegram_id"],
                f"📢 <b>Сообщение категории «{cat['name']}»</b>\n\n{text}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            pass
    log_admin_action(
        callback.from_user.id,
        "Рассылка категории",
        f"cat={cat['name']} sent={sent}/{len(members)}",
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ Отправлено: <b>{sent}</b> из <b>{len(members)}</b>.",
        reply_markup=category_detail_keyboard(category_id), parse_mode="HTML",
    )
    await callback.answer()


# Статистика категории

@router.callback_query(F.data.startswith("cat_stats:"))
async def category_stats(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    stats = await queries.get_category_stats(category_id)
    last = format_datetime(stats["last_salary"]) if stats["last_salary"] else "—"
    top = f"{stats['top_member']} ({stats['top_amount']:g} ⭐)" if stats["top_member"] else "—"
    text = (
        f"📊 <b>Статистика — {cat['name']}</b>\n\n"
        f"👥 Сотрудников: <b>{stats['members']}</b>\n"
        f"⭐ Всего начислено: <b>{stats['total_salary']:g}</b>\n"
        f"⚠️ Всего штрафов: <b>{stats['total_penalty']:g}</b>\n"
        f"📅 Последняя зарплата: <b>{last}</b>\n"
        f"🏆 Самый активный: <b>{top}</b>"
    )
    await callback.message.edit_text(
        text, reply_markup=category_detail_keyboard(category_id), parse_mode="HTML",
    )
    await callback.answer()


# История

@router.callback_query(F.data.startswith("cat_history:"))
async def category_history(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    ops = await queries.get_category_operations(category_id, limit=20)
    if not ops:
        text = f"📜 <b>История — {cat['name']}</b>\n\nПока пусто."
    else:
        lines = [f"📜 <b>История — {cat['name']}</b>\n"]
        for op in ops:
            date = format_datetime(op["created_at"])
            actor = op.get("performer_nickname") or str(op.get("performed_by") or "—")
            if op["operation_type"] == "salary":
                icon = "💰"
                label = "Зарплата"
            else:
                icon = "⚠️"
                label = "Штраф"
            scope = "всей категории" if op["scope"] == "category" else "одному"
            lines.append(
                f"{icon} <b>{label}</b> ({scope})\n"
                f"   📅 {date} · 👑 {actor}\n"
                f"   База: {op['base_amount']:g} · Итог: <b>{op['total_amount']:g}</b> "
                f"· 👥 {op['recipients_count']}"
            )
        text = "\n\n".join(lines)
    await callback.message.edit_text(
        text, reply_markup=category_history_keyboard(category_id), parse_mode="HTML",
    )
    await callback.answer()


# Коэффициенты категорий

@router.callback_query(F.data == "admin_cat_coefs")
async def cat_coefs_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    await state.clear()
    cats = await queries.get_all_staff_categories()
    if not cats:
        return await callback.answer("Категорий пока нет.", show_alert=True)
    lines = ["⚙️ <b>Коэффициенты категорий</b>\n"]
    for c in cats:
        lines.append(f"{c['name']} — <b>×{c['coefficient']:g}</b>")
    lines.append("\nНажмите категорию, чтобы изменить.")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=category_coefs_keyboard(cats),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_coef_edit:"))
async def cat_coef_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        return await callback.answer("No access.", show_alert=True)
    category_id = int(callback.data.split(":")[1])
    cat = await queries.get_staff_category(category_id)
    if not cat:
        return await callback.answer("Категория не найдена.", show_alert=True)
    await state.set_state(CategoryCoefEdit.waiting_value)
    await state.update_data(category_id=category_id)
    await callback.message.edit_text(
        f"⚙️ <b>Коэффициент — {cat['name']}</b>\n\n"
        f"Текущий: <b>×{cat['coefficient']:g}</b>\n\nВведите новое значение:",
        reply_markup=cancel_admin_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.message(CategoryCoefEdit.waiting_value)
async def cat_coef_apply(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id):
        return
    try:
        value = float(message.text.strip().replace(",", "."))
        if value <= 0:
            raise ValueError
    except ValueError:
        return await message.answer(
            "⚠️ Введите положительное число.",
            reply_markup=cancel_admin_keyboard(),
        )
    data = await state.get_data()
    category_id = data["category_id"]
    cat_before = await queries.get_staff_category(category_id)
    await queries.update_staff_category(category_id, coefficient=value)
    await state.clear()
    log_admin_action(
        message.from_user.id,
        "Изменение коэф. категории",
        f"cat={cat_before['name']} {cat_before['coefficient']:g} → {value:g}",
    )
    cats = await queries.get_all_staff_categories()
    lines = [
        f"✅ <b>{cat_before['name']}</b>: <b>×{value:g}</b>\n",
        "⚙️ <b>Коэффициенты категорий</b>\n",
    ]
    for c in cats:
        lines.append(f"{c['name']} — <b>×{c['coefficient']:g}</b>")
    await message.answer(
        "\n".join(lines),
        reply_markup=category_coefs_keyboard(cats),
        parse_mode="HTML",
    )
