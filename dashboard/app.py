"""
FastAPI-приложение: страницы, API, SSE-стрим логов.

Запуск:
    python -m dashboard.app
или через run-dashboard.bat.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard import auth, db, logs

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="VGS Money Dashboard", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
async def _ensure_schema() -> None:
    # Гарантируем, что миграции бота применены к БД — иначе на свежей
    # или ещё не мигрированной базе часть SELECT'ов упадёт.
    from bot.database.models import init_db
    try:
        await init_db()
    except Exception as e:  # не блокируем запуск дашборда, просто логируем
        print(f"[dashboard] init_db warning: {e}")


# ---------- Аутентификация ----------

def require_auth(request: Request) -> None:
    raw = request.cookies.get(auth.SESSION_COOKIE)
    if not auth.verify_cookie(raw):
        raise HTTPException(status_code=401, detail="unauthorized")


def is_authed(request: Request) -> bool:
    return auth.verify_cookie(request.cookies.get(auth.SESSION_COOKIE))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authed(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_submit(request: Request, password: str = Form(...)):
    if not auth.check_password(password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Неверный пароль"}, status_code=401
        )
    token = auth.issue_session_token()
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(
        auth.SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
    )
    return resp


@app.post("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


# ---------- Главная ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request})


# ---------- API: overview ----------

@app.get("/api/overview")
async def api_overview(_: None = Depends(require_auth)):
    total_users = db.query_scalar("SELECT COUNT(*) FROM users") or 0
    active_users = db.query_scalar("SELECT COUNT(*) FROM users WHERE is_blocked=0") or 0
    blocked_manual = db.query_scalar("SELECT COUNT(*) FROM users WHERE is_blocked=1") or 0
    blocked_auto = db.query_scalar("SELECT COUNT(*) FROM users WHERE is_blocked=2") or 0

    tx_today = db.query_scalar(
        "SELECT COUNT(*) FROM transactions WHERE date(created_at)=date('now')"
    ) or 0
    tx_total = db.query_scalar("SELECT COUNT(*) FROM transactions") or 0

    pending_requests = db.query_scalar(
        "SELECT COUNT(*) FROM requests WHERE status='pending'"
    ) or 0
    pending_orders = db.query_scalar(
        "SELECT COUNT(*) FROM shop_orders WHERE status='pending'"
    ) or 0
    active_quests = db.query_scalar(
        "SELECT COUNT(*) FROM quests WHERE status='active'"
    ) or 0
    staff_count = db.query_scalar(
        "SELECT COUNT(*) FROM staff WHERE is_active=1"
    ) or 0

    points_total = db.query_scalar("SELECT COALESCE(SUM(points),0) FROM users") or 0
    points_added_today = db.query_scalar(
        "SELECT COALESCE(SUM(amount),0) FROM transactions "
        "WHERE currency_type='points' AND operation='add' AND date(created_at)=date('now')"
    ) or 0

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "blocked_manual": blocked_manual,
            "blocked_auto": blocked_auto,
        },
        "transactions": {"today": tx_today, "total": tx_total},
        "requests": {"pending": pending_requests},
        "orders": {"pending": pending_orders},
        "quests": {"active": active_quests},
        "staff": {"active": staff_count},
        "points": {"total": points_total, "added_today": points_added_today},
    }


@app.get("/api/timeseries")
async def api_timeseries(days: int = 14, _: None = Depends(require_auth)):
    days = max(1, min(days, 90))
    regs = db.query_all(
        """
        SELECT date(registered_at) AS d, COUNT(*) AS c
        FROM users
        WHERE registered_at >= date('now', ?)
        GROUP BY date(registered_at)
        ORDER BY d
        """,
        (f"-{days} days",),
    )
    tx = db.query_all(
        """
        SELECT date(created_at) AS d, COUNT(*) AS c
        FROM transactions
        WHERE created_at >= date('now', ?)
        GROUP BY date(created_at)
        ORDER BY d
        """,
        (f"-{days} days",),
    )
    reqs = db.query_all(
        """
        SELECT date(created_at) AS d, status, COUNT(*) AS c
        FROM requests
        WHERE created_at >= date('now', ?)
        GROUP BY date(created_at), status
        ORDER BY d
        """,
        (f"-{days} days",),
    )
    return {"registrations": regs, "transactions": tx, "requests": reqs}


@app.get("/api/clubs")
async def api_clubs(_: None = Depends(require_auth)):
    return db.query_all(
        """
        SELECT COALESCE(club_name, '—') AS club, COUNT(*) AS c
        FROM users
        GROUP BY club_name
        ORDER BY c DESC
        """
    )


# ---------- API: users ----------

@app.get("/api/users")
async def api_users(
    q: str = "",
    blocked: str = "",
    limit: int = 50,
    offset: int = 0,
    order: str = "points",
    _: None = Depends(require_auth),
):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    where = []
    params: list = []
    if q:
        where.append("(nickname LIKE ? OR username LIKE ? OR player_tag LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like, like]
    if blocked in ("0", "1", "2"):
        where.append("is_blocked = ?")
        params.append(int(blocked))

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    order_columns = {
        "points": "points DESC",
        "registered_at": "registered_at DESC",
        "approved_requests": "approved_requests DESC",
        "nickname": "nickname COLLATE NOCASE ASC",
    }
    order_sql = order_columns.get(order, "points DESC")

    total = db.query_scalar(f"SELECT COUNT(*) FROM users {where_sql}", params) or 0
    rows = db.query_all(
        f"""
        SELECT telegram_id, username, nickname, player_tag, club_name,
               points, tickets_platinum, tickets_gold, tickets_silver, tickets_bronze,
               tickets_support, tickets_help, unwarns, unmutes, is_blocked,
               registered_at, approved_requests
        FROM users
        {where_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    return {"total": total, "rows": rows}


@app.get("/api/user/{telegram_id}")
async def api_user(telegram_id: int, _: None = Depends(require_auth)):
    user = db.query_one("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    if not user:
        raise HTTPException(status_code=404, detail="not found")
    user_pk = user["id"]
    tx = db.query_all(
        """
        SELECT id, currency_type, operation, amount, reason, performed_by, created_at
        FROM transactions
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 100
        """,
        (user_pk,),
    )
    reqs = db.query_all(
        """
        SELECT id, currency_type, amount, reason, status, created_at, reviewed_at, reviewed_by
        FROM requests
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 50
        """,
        (user_pk,),
    )
    return {"user": user, "transactions": tx, "requests": reqs}


# ---------- API: transactions ----------

@app.get("/api/transactions")
async def api_transactions(
    currency: str = "",
    operation: str = "",
    limit: int = 100,
    offset: int = 0,
    _: None = Depends(require_auth),
):
    limit = max(1, min(limit, 500))
    where = []
    params: list = []
    allowed_currency = {
        "points", "tickets_platinum", "tickets_gold", "tickets_silver",
        "tickets_bronze", "tickets_support", "tickets_help", "unwarns", "unmutes",
    }
    allowed_op = {"add", "subtract", "set"}
    if currency in allowed_currency:
        where.append("t.currency_type=?"); params.append(currency)
    if operation in allowed_op:
        where.append("t.operation=?"); params.append(operation)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = db.query_scalar(f"SELECT COUNT(*) FROM transactions t {where_sql}", params) or 0
    rows = db.query_all(
        f"""
        SELECT t.id, t.currency_type, t.operation, t.amount, t.reason,
               t.performed_by, t.created_at,
               u.telegram_id, u.nickname, u.username
        FROM transactions t
        LEFT JOIN users u ON u.id = t.user_id
        {where_sql}
        ORDER BY t.id DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    return {"total": total, "rows": rows}


# ---------- API: requests / orders / quests ----------

@app.get("/api/requests")
async def api_requests(status: str = "", limit: int = 100, offset: int = 0,
                       _: None = Depends(require_auth)):
    limit = max(1, min(limit, 500))
    where = []
    params: list = []
    if status in ("pending", "approved", "rejected"):
        where.append("r.status=?"); params.append(status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    total = db.query_scalar(f"SELECT COUNT(*) FROM requests r {where_sql}", params) or 0
    rows = db.query_all(
        f"""
        SELECT r.id, r.currency_type, r.amount, r.reason, r.status,
               r.created_at, r.reviewed_at, r.reviewed_by,
               u.telegram_id, u.nickname, u.username
        FROM requests r
        LEFT JOIN users u ON u.id = r.user_id
        {where_sql}
        ORDER BY r.id DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    return {"total": total, "rows": rows}


@app.get("/api/orders")
async def api_orders(status: str = "", limit: int = 100, offset: int = 0,
                     _: None = Depends(require_auth)):
    limit = max(1, min(limit, 500))
    where = []
    params: list = []
    if status in ("pending", "completed", "ignored"):
        where.append("o.status=?"); params.append(status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    total = db.query_scalar(f"SELECT COUNT(*) FROM shop_orders o {where_sql}", params) or 0
    rows = db.query_all(
        f"""
        SELECT o.id, o.order_type, o.details, o.status, o.created_at, o.completed_at,
               u.telegram_id, u.nickname, u.username
        FROM shop_orders o
        LEFT JOIN users u ON u.id = o.user_id
        {where_sql}
        ORDER BY o.id DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )
    return {"total": total, "rows": rows}


@app.get("/api/quests")
async def api_quests(status: str = "", _: None = Depends(require_auth)):
    where = []
    params: list = []
    if status in ("active", "closed"):
        where.append("q.status=?"); params.append(status)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    quests = db.query_all(
        f"""
        SELECT q.*,
               (SELECT COUNT(*) FROM quest_assignments a WHERE a.quest_id=q.id) AS taken,
               (SELECT COUNT(*) FROM quest_assignments a WHERE a.quest_id=q.id AND a.status='approved') AS approved,
               (SELECT COUNT(*) FROM quest_assignments a WHERE a.quest_id=q.id AND a.status='submitted') AS pending
        FROM quests q
        {where_sql}
        ORDER BY q.id DESC
        LIMIT 200
        """,
        params,
    )
    return quests


# ---------- API: логи ----------

@app.get("/api/logs/tail")
async def api_logs_tail(n: int = 500, _: None = Depends(require_auth)):
    n = max(10, min(n, 5000))
    return {"lines": logs.tail_lines(n)}


@app.get("/api/logs/days")
async def api_logs_days(_: None = Depends(require_auth)):
    return {"days": logs.list_log_days()}


@app.get("/api/logs/day/{day}")
async def api_logs_day(day: str, _: None = Depends(require_auth)):
    if not len(day) == 10 or day[4] != "-" or day[7] != "-":
        raise HTTPException(status_code=400, detail="bad day")
    return {"lines": logs.read_day(day)}


@app.get("/api/logs/stream")
async def api_logs_stream(request: Request):
    if not is_authed(request):
        raise HTTPException(status_code=401, detail="unauthorized")

    async def event_gen():
        # первичный дамп последних строк
        for line in logs.tail_lines(200):
            yield f"data: {json.dumps({'line': line})}\n\n"
        try:
            async for line in logs.stream_lines():
                if await request.is_disconnected():
                    break
                yield f"data: {json.dumps({'line': line})}\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- Точка входа ----------

def _run() -> None:
    import uvicorn

    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT", "8787"))
    uvicorn.run("dashboard.app:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    _run()
