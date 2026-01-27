import asyncio
from collections import defaultdict
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
import pytz
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import setup_logging, settings
from app.db import SessionLocal
from app.models import Settler, User, Settlement
from app.mfunc import get_timezones_at_hour

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Kiev'))
logger = logging.getLogger(__name__)
log = setup_logging(logger)

async def availability_check():
    log.debug("🔵 Online!")

async def remind_overtime():
    target_hour = 19 
    target_timezones = get_timezones_at_hour(target_hour)

    if not target_timezones:
        return

    async with SessionLocal() as session:
        try:
            stmt = (
                select(Settler)
                .join(User, Settler.user_id == User.id)
                .join(Settlement, Settler.settlement_id == Settlement.id)
                .where(
                    User.timezone.in_(target_timezones),
                    Settler.overtime_is_toggled == True,
                    Settler.quote_is_completed == False
                )
                .options(
                    selectinload(Settler.user),
                    selectinload(Settler.settlement)
                )
            )
            
            result = await session.execute(stmt)
            settlers = result.scalars().all()

        except Exception as e:
            log.error(f"Ошибка при выборке для remind_overtime: {e}")
            return

        if not settlers:
            return

        log.info(f"🔔 Подготовка напоминаний для зон {target_timezones[:3]}... ({len(settlers)} чел.)")

        chats_map = defaultdict(list)
        for settler in settlers:
            chats_map[settler.settlement.chat_id].append(settler)

        BATCH_SIZE = 5

        for chat_id, chat_members in chats_map.items():
            for i in range(0, len(chat_members), BATCH_SIZE):
                batch = chat_members[i : i + BATCH_SIZE]
                
                mentions = []
                for s in batch:
                    user_link = f"<a href='tg://user?id={s.user.telegram_id}'>{s.user.name}</a>"
                    mentions.append(f"• {user_link} ({s.quote}/{s.target_quote})")
                
                text = "⏰ <b>Не забудьте выполнить лишнюю меру!</b>\n" + "\n".join(mentions)

                try:
                    await bot.send_message(chat_id, text)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    log.error(f"Ошибка при отправке батча в чат {chat_id}: {e}")

async def day_reset():
    target_timezones = get_timezones_at_hour(0)
    
    if not target_timezones:
        log.debug("🕐 Час прошел, но полночь нигде из активных зон не наступила (редкий кейс).")
        return

    async with SessionLocal() as session:
        log.info(f"↪️ Запуск почасового сброса для зон: {target_timezones[:5]}...")
        
        try:
            stmt = (
                select(Settler)
                .join(User, Settler.user_id == User.id)
                .where(User.timezone.in_(target_timezones))
            )
            
            result = await session.execute(stmt)
            settlers = result.scalars().all()
            
            if not settlers:
                log.debug("🕐 В текущих часовых поясах нет активных игроков.")
                return

        except Exception as e:
            log.error(f"Ошибка при выборке поселенцев для сброса: {e}")
            return
        
        log.info(f"🔄 Сброс выполняется для {len(settlers)} поселенцев...")

        try:
            overtime_settlers = [s for s in settlers if s.overtime_is_toggled and not s.quote_is_completed]
            
            for settler in overtime_settlers:
                fine = 20 + settler.level
                settler.balance -= fine
                
                user_result = await session.execute(select(User).where(User.id == settler.user_id))
                user = user_result.scalars().first()
                if user:
                    mention = f"<a href='tg://user?id={user.telegram_id}'>{user.name}</a>"
                    settlement_result = await session.execute(
                        select(Settlement).where(Settlement.id == settler.settlement_id)
                    )
                    settlement = settlement_result.scalars().first()
                    if settlement:
                        await bot.send_message(settlement.chat_id, f"⚠️ <b>{mention} не поспел(а) свершить лишнюю меру!</b> Вира наложена: 💰 <b>{fine}</b>. Впредь будь расторопнее!", disable_notification=False)
            
            ids_to_update = [s.id for s in settlers]
            
            if ids_to_update:
                await session.execute(
                    update(Settler)
                    .where(Settler.id.in_(ids_to_update))
                    .values(
                        quote=0,
                        quote_is_completed=False,
                        overtime_count=0,
                        overtime_is_toggled=False
                    )
                )

                for settler in settlers:
                    settler.target_quote = round(settler.level * 0.85 + 6)

        except Exception as e:
            log.error(f"Ошибка при выполнении сброса: {e}")
            return
        
        await session.commit()
        log.info(f"✅ Сброс завершен для {len(settlers)} игроков.")