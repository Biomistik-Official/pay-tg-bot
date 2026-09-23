"""
FSM States для всех форм ввода бота.
"""

from aiogram.fsm.state import State, StatesGroup


# Регистрация нового пользователя
class Registration(StatesGroup):
    waiting_nickname = State()
    waiting_player_tag = State()


# Изменение тега Brawl Stars (Admin)
class ChangePlayerTag(StatesGroup):
    waiting_new_tag = State()


# Запрос тикетов пользователем
class RequestTickets(StatesGroup):
    waiting_ticket_type = State()   # выбор типа тикета (кнопкой)
    waiting_amount      = State()   # количество тикетов
    waiting_reason      = State()   # причина получения


# Запрос баллов пользователем
class RequestPoints(StatesGroup):
    waiting_amount = State()
    waiting_reason = State()


# Поиск пользователя (Admin)
class SearchUser(StatesGroup):
    waiting_query = State()


# Изменение никнейма пользователя (Admin)
class ChangeNickname(StatesGroup):
    waiting_new_nickname = State()


# Управление тикетами (Admin)
class ManageTickets(StatesGroup):
    waiting_user_id = State()
    waiting_ticket_type = State()
    waiting_amount = State()
    waiting_reason = State()


# Управление баллами (Admin)
class ManagePoints(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()
    waiting_reason = State()


# Изменение баланса (Admin)
class SetBalance(StatesGroup):
    waiting_user_id = State()
    waiting_ticket_type = State()
    waiting_amount = State()


# Магазин: обмен баллов на тикеты
class ShopExchange(StatesGroup):
    waiting_ticket_type = State()   # выбор типа тикета
    waiting_amount      = State()   # ввод количества баллов
    confirm             = State()   # подтверждение


# Магазин: вывод баллов в деньги
class ShopWithdraw(StatesGroup):
    waiting_amount = State()   # ввод количества баллов
    confirm        = State()   # подтверждение


# Админ: настройки магазина
class AdminShopSettings(StatesGroup):
    waiting_withdraw_rate = State()   # ввод нового курса
    waiting_withdraw_min  = State()   # ввод нового минимума
    waiting_roulette_cost = State()   # ввод стоимости рулетки
    waiting_ticket_price  = State()   # ввод цены тикета в баллах


# Управление Staff (Admin)
class ManageStaff(StatesGroup):
    waiting_user_search = State()   # поиск по нику/ID для добавления


# Отклонение заявки на тикеты/баллы (Admin — причина)
class RejectRequest(StatesGroup):
    waiting_reason = State()


# Объявления (Admin)
class AdminAnnouncement(StatesGroup):
    waiting_text    = State()
    confirm         = State()


# Управление модерацией (Admin)
class ManageModeration(StatesGroup):
    waiting_amount = State()


# Управление админ-валютами: рубли, звёзды (Admin)
class ManageAdminCurrency(StatesGroup):
    waiting_amount = State()
    waiting_reason = State()




class TreasuryTopUp(StatesGroup):
    waiting_amount = State()
    waiting_manual_amount = State()
    waiting_reason = State()
    confirm = State()


class TreasuryDonation(StatesGroup):
    waiting_amount = State()
    waiting_reason = State()
    confirm = State()


class TreasurySpend(StatesGroup):
    waiting_amount = State()
    waiting_reason = State()
    confirm = State()


class TreasuryDistribution(StatesGroup):
    waiting_amount = State()
    confirm = State()


class TreasuryPercentages(StatesGroup):
    waiting_values = State()


class TreasuryMemberAdd(StatesGroup):
    waiting_search = State()


class TreasuryPayout(StatesGroup):
    waiting_amount = State()
    confirm = State()

