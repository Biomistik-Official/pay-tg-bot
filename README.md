# 🏆 VGS Money

Telegram-бот для управления внутренней валютой.

**Валюты:** 🎫 Тикеты и ⭐ Баллы

---

## 📋 Возможности

### 👤 Для участников
- Регистрация с игровым никнеймом
- Просмотр своего профиля и баланса
- История всех операций с пагинацией
- Запрос тикетов / баллов с причиной
- Уведомления о решении по заявке

### 👑 Для владельца (Admin-панель)
- Управление пользователями (поиск, блокировка, смена ника)
- Выдача / снятие / установка баланса тикетов и баллов
- Просмотр и обработка заявок в реальном времени
- История всех заявок с пагинацией
- Общая статистика системы
- Логирование всех действий в файл

---

## 🚀 Установка и запуск

### 1. Требования

- Python **3.12+**
- pip

### 2. Создать виртуальное окружение

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения

Скопировать `.env.example` в `.env`:

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Открыть `.env` и заполнить:

```env
BOT_TOKEN=1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx
OWNER_ID=123456789
DAILY_REQUEST_LIMIT=3
DATABASE_PATH=bot/database/club_bot.db
```

**Где взять значения:**

| Переменная | Как получить |
|---|---|
| `BOT_TOKEN` | Написать @BotFather → /newbot |
| `OWNER_ID` | Написать @userinfobot |
| `DAILY_REQUEST_LIMIT` | Любое число (рекомендуется 3) |
| `DATABASE_PATH` | Оставить по умолчанию |

### 5. Запустить бота

```bash
python -m bot.main
```

> При первом запуске база данных создаётся автоматически.

---

## 📁 Структура проекта

```
control tg bot/
├── bot/
│   ├── main.py
│   ├── config.py
│   ├── database/
│   │   ├── models.py
│   │   └── queries.py
│   ├── handlers/
│   │   ├── start.py
│   │   ├── profile.py
│   │   ├── currency.py
│   │   ├── requests.py
│   │   ├── history.py
│   │   └── admin/
│   │       ├── panel.py
│   │       ├── users.py
│   │       ├── tickets.py
│   │       ├── points.py
│   │       ├── requests.py
│   │       └── stats.py
│   ├── keyboards/
│   │   ├── user.py
│   │   └── admin.py
│   ├── states/
│   │   └── forms.py
│   ├── middlewares/
│   │   └── throttling.py
│   └── utils/
│       ├── logger.py
│       └── formatters.py
├── logs/
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🗄️ База данных

SQLite файл создаётся автоматически. Таблицы:

| Таблица | Описание |
|---|---|
| `users` | Пользователи (TG ID, ник, баланс, блокировка) |
| `transactions` | История операций с валютой |
| `requests` | Заявки на получение валюты |

---

## ⚙️ Настройки

| Параметр | По умолчанию | Описание |
|---|---|---|
| `DAILY_REQUEST_LIMIT` | `3` | Максимум заявок в день на пользователя |
| `DATABASE_PATH` | `bot/database/club_bot.db` | Путь к файлу БД |

---

## 📝 Логирование

Логи сохраняются в папку `logs/` с именем вида `bot_2026-06-17.log`.

Каждое действие владельца фиксируется:
```
2026-06-17 18:00:00 | INFO | [OWNER:123456] APPROVE_REQUEST | #42 | PlayerNick | 50 tickets
```

---

## 🛡️ Защита

- **Throttling**: не более 1 сообщения в секунду на пользователя
- **Лимит заявок**: максимум N заявок в день (настраивается)
- **Блокировка**: заблокированные пользователи не могут использовать бота
- **Проверка прав**: все Admin-функции проверяют OWNER_ID
- **Валидация**: все вводимые числа проверяются на корректность

---

## 🔄 Остановка бота

Нажать `Ctrl+C` в терминале.
