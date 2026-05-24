import asyncio
from datetime import datetime
import database as db
from config import ADMIN_IDS, TOTAL_TICKETS, PRIZE_INFO


async def check_and_run_lottery(bot):
    """Фоновая задача - проверяет каждую минуту условия для розыгрыша"""
    while True:
        try:
            status = await db.get_current_lottery_status()
            if status:
                sold, is_active, started_at = status

                timer_info = await db.get_lottery_timer()
                timer_start, timer_end, is_timer_active = timer_info if timer_info else (None, None, False)

                should_draw = False
                reason = ""

                if sold >= TOTAL_TICKETS and is_active:
                    should_draw = True
                    reason = "Проданы все 100 билетов"
                    if is_timer_active:
                        await db.stop_lottery_timer()

                elif is_timer_active and timer_end:
                    end_time = datetime.fromisoformat(timer_end) if isinstance(timer_end, str) else timer_end
                    if datetime.now() >= end_time:
                        should_draw = True
                        reason = "Истекло 4 дня"
                        await db.stop_lottery_timer()

                elif sold >= 70 and not is_timer_active and is_active and sold < TOTAL_TICKETS:
                    await db.start_lottery_timer()
                    print(f"✅ ЗАПУЩЕН ТАЙМЕР НА 4 ДНЯ! Продано {sold} билетов")

                    for admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(
                                admin_id,
                                f"⏰ ЗАПУЩЕН ТАЙМЕР НА 4 ДНЯ!\n\n"
                                f"Продано {sold}/{TOTAL_TICKETS} билетов\n"
                                f"Розыгрыш состоится через 4 дня!"
                            )
                        except:
                            pass

                if should_draw and is_active:
                    winner = await db.start_lottery_draw()
                    if winner:
                        try:
                            await bot.send_message(
                                winner["user_id"],
                                f"""
🎉🎉🎉 ПОЗДРАВЛЯЕМ! ВЫ ПОБЕДИТЕЛЬ! 🎉🎉🎉

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ВЫ ВЫИГРАЛИ {PRIZE_INFO['name']}!!!

🏆 ВАШ БИЛЕТ №{winner['ticket']} ОКАЗАЛСЯ ПОБЕДНЫМ!

📦 ПРИЗ: {PRIZE_INFO['name']}
📝 ОПИСАНИЕ: {PRIZE_INFO['description']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
С ВАМИ СВЯЖЕТСЯ МЕНЕДЖЕР 
В БЛИЖАЙШЕЕ ВРЕМЯ ДЛЯ ВРУЧЕНИЯ ПРИЗА!

Спасибо за участие! 🙏
"""
                            )
                        except:
                            pass

                        for admin_id in ADMIN_IDS:
                            try:
                                await bot.send_message(
                                    admin_id,
                                    f"""
🏆🏆🏆 РОЗЫГРЫШ СОСТОЯЛСЯ! 🏆🏆🏆

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ПОБЕДИТЕЛЬ:
👤 ID: {winner['user_id']}
🎫 Билет: №{winner['ticket']}
🏆 Приз: {PRIZE_INFO['name']}

ПРИЧИНА: {reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❗️ СВЯЖИТЕСЬ С ПОБЕДИТЕЛЕМ ДЛЯ ВРУЧЕНИЯ ПРИЗА! ❗️
"""
                                )
                            except:
                                pass

        except Exception as e:
            print(f"Ошибка в lottery checker: {e}")

        await asyncio.sleep(60)
