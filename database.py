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
                registered_at TIMESTAMP,
                total_tickets_bought INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT NULL
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
                receipt_photo TEXT,
                price_paid INTEGER DEFAULT 800
            )
        """)

        # Реферальная система
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                referred_bought_ticket BOOLEAN DEFAULT 0,
                referral_date TIMESTAMP,
                free_ticket_given BOOLEAN DEFAULT 0
            )
        """)

        # Акции
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                promo_type TEXT,
                user_id INTEGER,
                triggered_at TIMESTAMP,
                reward_given BOOLEAN DEFAULT 0
            )
        """)

        # Текущий розыгрыш
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

        cursor = await db.execute("SELECT * FROM current_lottery WHERE id = 1")
        if not await cursor.fetchone():
            await db.execute("""
                INSERT INTO current_lottery (id, started_at, tickets_sold, is_active, is_timer_active)
                VALUES (1, ?, 0, 1, 0)
            """, (datetime.now(),))
            await db.commit()


async def add_user(user_id: int, username: str, full_name: str, referrer_id: int = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name, registered_at, referrer_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, full_name, datetime.now(), referrer_id))
        await db.commit()


async def add_subscription(user_id: int, ticket_number: int, receipt_photo: str, price: int):
    expires_at = datetime.now() + timedelta(days=10)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO subscriptions (user_id, ticket_number, purchase_date, expires_at, receipt_photo, price_paid)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, ticket_number, datetime.now(), expires_at, receipt_photo, price))
        await db.commit()


async def confirm_payment(subscription_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE subscriptions SET payment_confirmed = 1 WHERE id = ?
        """, (subscription_id,))

        cursor = await db.execute("SELECT user_id, ticket_number FROM subscriptions WHERE id = ?", (subscription_id,))
        user_id, ticket_num = await cursor.fetchone()

        await db.execute("""
            UPDATE users SET total_tickets_bought = total_tickets_bought + 1 WHERE user_id = ?
        """, (user_id,))

        await db.execute("""
            UPDATE current_lottery SET tickets_sold = tickets_sold + 1 WHERE id = 1
        """)

        cursor = await db.execute("SELECT tickets_sold FROM current_lottery WHERE id = 1")
        sold = await cursor.fetchone()

        await db.commit()
        return sold[0] if sold else 0, user_id, ticket_num


async def get_user_ticket_count(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT total_tickets_bought FROM users WHERE user_id = ?
        """, (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else 0


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
            SELECT user_id, ticket_number, receipt_photo, price_paid 
            FROM subscriptions WHERE id = ? AND payment_confirmed = 0
        """, (subscription_id,))
        return await cursor.fetchone()


async def delete_subscription(subscription_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))
        await db.commit()


# ========== РЕФЕРАЛЬНАЯ СИСТЕМА ==========

async def add_referral(referrer_id: int, referred_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO referrals (referrer_id, referred_id, referral_date)
            VALUES (?, ?, ?)
        """, (referrer_id, referred_id, datetime.now()))
        await db.commit()


async def mark_referral_bought(referred_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE referrals SET referred_bought_ticket = 1 WHERE referred_id = ?
        """, (referred_id,))
        await db.commit()


async def get_referrals_count(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM referrals 
            WHERE referrer_id = ? AND referred_bought_ticket = 1
        """, (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else 0


async def get_referral_list(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT r.referred_id, u.username, r.referred_bought_ticket, r.referral_date
            FROM referrals r
            JOIN users u ON r.referred_id = u.user_id
            WHERE r.referrer_id = ?
        """, (user_id,))
        return await cursor.fetchall()


async def get_five_referrals_count(user_id: int):
    """Проверка на 5 приведенных друзей"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM referrals 
            WHERE referrer_id = ? AND referred_bought_ticket = 1
        """, (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else 0


async def check_and_give_free_ticket_for_5_referrals(user_id: int):
    """Акция: за 5 приведенных друзей - бесплатный билет"""
    count = await get_five_referrals_count(user_id)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT id FROM promotions 
            WHERE user_id = ? AND promo_type = '5_referrals' AND reward_given = 1
        """, (user_id,))
        already_given = await cursor.fetchone()

        if count >= 5 and not already_given:
            await db.execute("""
                INSERT INTO promotions (promo_type, user_id, triggered_at, reward_given)
                VALUES ('5_referrals', ?, ?, 1)
            """, (user_id, datetime.now()))
            await db.commit()
            return True
    return False


async def mark_referral_free_ticket_given(user_id: int, referred_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE referrals SET free_ticket_given = 1 
            WHERE referrer_id = ? AND referred_id = ?
        """, (user_id, referred_id))
        await db.commit()


async def get_lottery_timer():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT timer_start, timer_end, is_timer_active FROM current_lottery WHERE id = 1
        """)
        return await cursor.fetchone()


async def start_lottery_timer():
    timer_start = datetime.now()
    timer_end = timer_start + timedelta(days=4)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE current_lottery SET 
                timer_start = ?, timer_end = ?, is_timer_active = 1
            WHERE id = 1
        """, (timer_start, timer_end))
        await db.commit()


async def stop_lottery_timer():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE current_lottery SET 
                is_timer_active = 0, timer_start = NULL, timer_end = NULL
            WHERE id = 1
        """)
        await db.commit()


async def get_last_winner():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT winner_id, winner_ticket, draw_date FROM lottery_history 
            ORDER BY draw_date DESC LIMIT 1
        """)
        return await cursor.fetchone()


async def get_timer_status():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            SELECT is_timer_active, timer_end FROM current_lottery WHERE id = 1
        """)
        return await cursor.fetchone()
