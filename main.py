import logging
import os
import sqlite3
import calendar
from datetime import date, datetime
from collections import defaultdict

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ── Config ─────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get('BOT_TOKEN')
DB_PATH   = "dnd_sessions.db"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown") # type: ignore

MONTH_NAMES = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

# ── Database ───────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                username     TEXT,
                full_name    TEXT,
                session_date TEXT NOT NULL,          -- ISO-8601  YYYY-MM-DD
                created_at   TEXT DEFAULT (datetime('now')),
                UNIQUE (user_id, session_date)       -- one row per user per day
            )
        """)
    log.info("Database ready at %s", DB_PATH)


def toggle_date(user_id: int, username: str, full_name: str, iso_date: str) -> bool:
    """Toggle a date for a user. Returns True when added, False when removed."""
    with get_db() as con:
        existing = con.execute(
            "SELECT id FROM sessions WHERE user_id=? AND session_date=?",
            (user_id, iso_date),
        ).fetchone()
        if existing:
            con.execute(
                "DELETE FROM sessions WHERE user_id=? AND session_date=?",
                (user_id, iso_date),
            )
            return False
        con.execute(
            "INSERT INTO sessions (user_id, username, full_name, session_date) VALUES (?,?,?,?)",
            (user_id, username, full_name, iso_date),
        )
        return True


def all_picked_dates() -> set[str]:
    with get_db() as con:
        rows = con.execute("SELECT DISTINCT session_date FROM sessions").fetchall()
    return {r["session_date"] for r in rows}


def user_picked_dates(user_id: int) -> set[str]:
    with get_db() as con:
        rows = con.execute(
            "SELECT session_date FROM sessions WHERE user_id=?", (user_id,)
        ).fetchall()
    return {r["session_date"] for r in rows}


def dates_in_month(year: int, month: int):
    with get_db() as con:
        return con.execute(
            """SELECT session_date, user_id, username, full_name
               FROM sessions
               WHERE session_date LIKE ?
               ORDER BY session_date""",
            (f"{year:04d}-{month:02d}-%",),
        ).fetchall()


def all_user_dates(user_id: int) -> list[str]:
    with get_db() as con:
        rows = con.execute(
            "SELECT session_date FROM sessions WHERE user_id=? ORDER BY session_date",
            (user_id,),
        ).fetchall()
    return [r["session_date"] for r in rows]


# ── Calendar builder ───────────────────────────────────────────────────────────

def build_calendar(year: int, month: int, user_id: int) -> InlineKeyboardMarkup:
    markup     = InlineKeyboardMarkup()
    user_picks = user_picked_dates(user_id)
    any_picks  = all_picked_dates()
    today      = date.today()

    # Header — prev / month+year label / next
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    next_y, next_m = (year, month + 1) if month < 12 else (year + 1, 1)

    markup.row(
        InlineKeyboardButton("◀", callback_data=f"CAL|nav|{prev_y}|{prev_m}"),
        InlineKeyboardButton(f"🪬 {MONTH_NAMES[month]} {year}", callback_data="CAL|noop"),
        InlineKeyboardButton("▶", callback_data=f"CAL|nav|{next_y}|{next_m}"),
    )

    # Weekday labels
    markup.row(*[
        InlineKeyboardButton(d, callback_data="CAL|noop")
        for d in ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
    ])

    # Day grid
    for week in calendar.monthcalendar(year, month):
        row_buttons = []
        for day in week:
            if day == 0:
                row_buttons.append(InlineKeyboardButton(" ", callback_data="CAL|noop"))
            else:
                iso = f"{year:04d}-{month:02d}-{day:02d}"
                if iso in user_picks:
                    label = f"✅{day}"
                elif iso in any_picks:
                    label = f"🗓{day}"
                elif date(year, month, day) < today:
                    label = f"·{day}·"
                else:
                    label = str(day)
                row_buttons.append(
                    InlineKeyboardButton(label, callback_data=f"CAL|day|{iso}")
                )
        markup.row(*row_buttons)

    # Footer
    markup.row(
        InlineKeyboardButton("📋 Помеченные Дни", callback_data=f"CAL|sched|{year}|{month}"),
        InlineKeyboardButton("👤 Мои Дни Силы",       callback_data="CAL|mydates"),
    )

    return markup


def build_schedule_text(year: int, month: int) -> str:
    rows = dates_in_month(year, month)
    if not rows:
        return (
            f"📅 *{MONTH_NAMES[month]} {year}*\n\n"
            "Лик грядущего сокрыт. Пошлите /start дабы призвать Оракула."
        )
    by_date: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        name = r["full_name"] or r["username"] or str(r["user_id"])
        by_date[r["session_date"]].append(name)

    counter = [(len(by_date[iso]),iso) for iso in by_date]

    lines = [f"📅 *{MONTH_NAMES[month]} {year}* — Помеченные Дни\n"]
    for count, iso in sorted(counter, reverse=True):
        d        = datetime.strptime(iso, "%Y-%m-%d")
        day_name = d.strftime("%A %d")
        players  = ", ".join(by_date[iso])
        lines.append(f"  🗡 *{day_name} * — *({count})* {players} ")
    return "\n".join(lines)


def build_schedule_markup(year: int, month: int) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    next_y, next_m = (year, month + 1) if month < 12 else (year + 1, 1)
    markup.row(
        InlineKeyboardButton(f"◀ {MONTH_NAMES[prev_m]}", callback_data=f"SCHED|{prev_y}|{prev_m}"),
        InlineKeyboardButton("🪬 Оракул Дат",               callback_data=f"BACK_CAL|{year}|{month}"),
        InlineKeyboardButton(f"{MONTH_NAMES[next_m]} ▶",  callback_data=f"SCHED|{next_y}|{next_m}"),
    )
    return markup


# ── Command handlers ───────────────────────────────────────────────────────────

@bot.message_handler(commands=["start", "calendar"])
def cmd_start(message):
    today  = date.today()
    markup = build_calendar(today.year, today.month, message.from_user.id)
    bot.send_message(
        message.chat.id,
        "🪬 *Оракул Дней Доблестных Героев - Покорителей Подземелий и Драконов*\n\n"
        "Заяви о своей силе в избранный день.\n"
        "✅ = Твое Слово  |  🗓 = Слово твоих Союзников\n\n"
        "/schedule — Обратить взор на откликнувшихся\n"
        "/mydates  — Открыть хронику своих решений",
        reply_markup=markup,
    )


@bot.message_handler(commands=["schedule"])
def cmd_schedule(message):
    args  = message.text.split()[1:]
    today = date.today()
    try:
        year  = int(args[0]) if args else today.year
        month = int(args[1]) if len(args) > 1 else today.month
        if not (1 <= month <= 12):
            raise ValueError
    except (ValueError, IndexError):
        year, month = today.year, today.month

    bot.send_message(
        message.chat.id,
        build_schedule_text(year, month),
        reply_markup=build_schedule_markup(year, month),
    )


@bot.message_handler(commands=["mydates"])
def cmd_mydates(message):
    user  = message.from_user
    dates = all_user_dates(user.id)

    if not dates:
        bot.send_message(
            message.chat.id,
            "Лик грядущего все еще сокрыт от тебя. Пошли /start для призыва Оракула.",
        )
        return

    by_month: dict[str, list[str]] = defaultdict(list)
    for iso in dates:
        by_month[iso[:7]].append(iso)

    first_name = user.first_name or "Преключенец"
    lines = [f"👤 *Ваши Дни Силы, {first_name}:*\n"]
    for ym in sorted(by_month):
        y, m = int(ym[:4]), int(ym[5:])
        lines.append(f"📅 *{MONTH_NAMES[m]} {y}*")
        for iso in by_month[ym]:
            d = datetime.strptime(iso, "%Y-%m-%d")
            lines.append(f"   • {d.strftime('%A, %B %d')}")
    lines.append(f"\n_Total: {len(dates)} session(s)_")

    bot.send_message(message.chat.id, "\n".join(lines))


# ── Callback query handler ─────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    parts  = call.data.split("|")
    tag    = parts[0]
    user   = call.from_user

    # ── Calendar actions ───────────────────────────────────────────────────────
    if tag == "CAL":
        action = parts[1]

        if action == "noop":
            bot.answer_callback_query(call.id)

        elif action == "nav":
            year, month = int(parts[2]), int(parts[3])
            markup = build_calendar(year, month, user.id)
            bot.answer_callback_query(call.id)
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=markup
            )

        elif action == "day":
            iso_date = parts[2]
            added    = toggle_date(
                user_id   = user.id,
                username  = user.username or "",
                full_name = user.full_name or "",
                iso_date  = iso_date,
            )
            d           = datetime.strptime(iso_date, "%Y-%m-%d")
            status_text = "Отмечено" if added else "Стерто"
            bot.answer_callback_query(
                call.id, f"{'✅' if added else '❌'} {status_text}: {d.strftime('%B %d, %Y')}"
            )
            markup = build_calendar(d.year, d.month, user.id)
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=markup
            )

        elif action == "sched":
            year, month = int(parts[2]), int(parts[3])
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                build_schedule_text(year, month),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=build_schedule_markup(year, month),
            )

        elif action == "mydates":
            dates = all_user_dates(user.id)
            if not dates:
                bot.answer_callback_query(call.id, "Ты еще не открыл своего будущего!", show_alert=True)
                return

            by_month: dict[str, list[str]] = defaultdict(list)
            for iso in dates:
                by_month[iso[:7]].append(iso)

            lines = ["Ваши дни силы:\n"]
            for ym in sorted(by_month):
                y, m = int(ym[:4]), int(ym[5:])
                lines.append(f"📅 {MONTH_NAMES[m]} {y}")
                for iso in by_month[ym]:
                    d2 = datetime.strptime(iso, "%Y-%m-%d")
                    lines.append(f"  • {d2.strftime('%a %d')}")
            bot.answer_callback_query(call.id, "\n".join(lines), show_alert=True)

    # ── Schedule month navigation ──────────────────────────────────────────────
    elif tag == "SCHED":
        year, month = int(parts[1]), int(parts[2])
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            build_schedule_text(year, month),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=build_schedule_markup(year, month),
        )

    # ── Back to calendar from schedule view ────────────────────────────────────
    elif tag == "BACK_CAL":
        year, month = int(parts[1]), int(parts[2])
        markup = build_calendar(year, month, user.id)
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "🪬 *Оракул Дней Доблестных Героев - Покорителей Подземелий и Драконов*\n\n"
            "Заяви о своей силе в избранный денью.\n"
            "✅ = Твое слово  |  🗓 = Слово твоих союзников",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
        )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    log.info("Bot is running — press Ctrl+C to stop.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)