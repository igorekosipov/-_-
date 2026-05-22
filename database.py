import aiosqlite
from datetime import datetime, timedelta

DATABASE_PATH = "lottery.db"


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Пользователи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                registered_at TIMESTAMP
            )
        """)

        # Подписки/билеты
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                ticket_number INTEGER,
                purchase_date TIMESTAMP,
                expires_at TIMESTAMP,
                payment_confirmed BOOLEAN DEFAULT 0,
                receipt_photo TEXT
            )
        """)

        # Текущий розыгрыш с полями для таймера
        await db.execute("""
            CREATE TABLE IF NOT EXISTS current_lottery (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                started_at TIMESTAMP,
                tickets_sold INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                timer_start TIMESTAMP,
                timer_end TIMESTAMP,
                is_timer_active BOOLEAN DEFAULT 0
            )
        """)

        # История розыгрышей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lottery_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draw_date TIMESTAMP,
                tickets_total INTEGER,
                winner_id INTEGER,
                winner_ticket INTEGER
            )
        """)

        await db.commit()

        # Создаем запись о текущем розыгрыше если её нет
        cursor = await db.execute("SELECT * FROM current_lottery WHERE id = 1")
        if not await cursor.fetchone():
            await db.execute("""
                INSERT INTO current_lottery (id, started_at, tickets_sold, is_active, is_timer_active)
                VALUES (1, ?, 0, 1, 0)
            """, (datetime.now(),))
            await db.commit()


async def add_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name, registered_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, full_name, datetime.now()))
        await db.commit()


async def add_subscription(user_id: int, ticket_number: int, receipt_photo: str):
    expires_at = datetime.now() + timedelta(days=10)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO subscriptions (user_id, ticket_number, purchase_date, expires_at, receipt_photo)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, ticket_number, datetime.now(), expires_at, receipt_photo))
        await db.commit()


async def confirm_payment(subscription_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE subscriptions SET payment_confirmed = 1 WHERE id = ?
        """, (subscription_id,))

        await db.execute("""
            UPDATE current_lottery SET tickets_sold = tickets_sold + 1 WHERE id = 1
        """)

        cursor = await db.execute("SELECT tickets_sold FROM current_lottery WHERE id = 1")
        sold = await cursor.fetchone()

        await db.commit()
        return sold[0] if sold else 0


async def get_user_tickets(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT ticket_number, purchase_date, payment_confirmed 
            FROM subscriptions 
            WHERE user_id = ? AND expires_at > ?
        """, (user_id, datetime.now()))
        return await cursor.fetchall()


async def get_all_active_tickets():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT s.user_id, s.ticket_number, u.username 
            FROM subscriptions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.payment_confirmed = 1 AND s.expires_at > ?
        """, (datetime.now(),))
        return await cursor.fetchall()


async def get_last_draw_winner():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT winner_ticket FROM lottery_history 
            ORDER BY draw_date DESC LIMIT 1
        """)
        return await cursor.fetchone()


async def get_current_lottery_status():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT tickets_sold, is_active, started_at FROM current_lottery WHERE id = 1
        """)
        return await cursor.fetchone()


async def start_lottery_draw():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, ticket_number FROM subscriptions 
            WHERE payment_confirmed = 1 AND expires_at > ?
        """, (datetime.now(),))
        tickets = await cursor.fetchall()

        if not tickets:
            return None

        import random
        winner = random.choice(tickets)

        await db.execute("""
            INSERT INTO lottery_history (draw_date, tickets_total, winner_id, winner_ticket)
            VALUES (?, ?, ?, ?)
        """, (datetime.now(), len(tickets), winner[0], winner[1]))

        await db.execute("""
            UPDATE current_lottery SET 
                started_at = ?, tickets_sold = 0, is_active = 1,
                timer_start = NULL, timer_end = NULL, is_timer_active = 0
            WHERE id = 1
        """, (datetime.now(),))

        await db.commit()
        return {"user_id": winner[0], "ticket": winner[1]}


async def cleanup_expired_subscriptions():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM subscriptions WHERE expires_at <= ?", (datetime.now(),))
        await db.commit()


async def get_pending_subscription(subscription_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, ticket_number, receipt_photo FROM subscriptions WHERE id = ? AND payment_confirmed = 0
        """, (subscription_id,))
        return await cursor.fetchone()


async def delete_subscription(subscription_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))
        await db.commit()


# ========== ФУНКЦИИ ДЛЯ ТАЙМЕРА ==========

async def get_lottery_timer():
    """Получить таймер обратного отсчета"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT timer_start, timer_end, is_timer_active 
            FROM current_lottery WHERE id = 1
        """)
        return await cursor.fetchone()


async def start_lottery_timer():
    """Запустить таймер на 4 дня"""
    timer_start = datetime.now()
    timer_end = timer_start + timedelta(days=4)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE current_lottery SET 
                timer_start = ?, 
                timer_end = ?, 
                is_timer_active = 1
            WHERE id = 1
        """, (timer_start, timer_end))
        await db.commit()


async def stop_lottery_timer():
    """Остановить таймер"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE current_lottery SET 
                is_timer_active = 0,
                timer_start = NULL,
                timer_end = NULL
            WHERE id = 1
        """)
        await db.commit()


async def get_last_winner():
    """Получить последнего победителя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT winner_id, winner_ticket, draw_date 
            FROM lottery_history 
            ORDER BY draw_date DESC LIMIT 1
        """)
        return await cursor.fetchone()


async def get_timer_status():
    """Получить статус таймера для отображения"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT is_timer_active, timer_end FROM current_lottery WHERE id = 1
        """)
        return await cursor.fetchone()
