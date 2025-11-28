from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
import pytz
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import setup_logging, settings
from db import SessionLocal
from models import Settler, User, Settlement

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Kiev'))
logger = logging.getLogger(__name__)
log = setup_logging(logger)

async def availability_check():
    log.debug("🔵 Online!")

async def reminder_overtime():
    async with SessionLocal() as session:
        try:
            result = await session.execute(select(Settler))
            settlers = result.scalars().all()
        except Exception as e:
            log.error(f"Ошибка при получении поселенцев для проверки овертайма: {e}")
            return
        
        for settler in settlers:
            if settler.overtime_is_toggled and not settler.quote_is_completed:
                try:
                    result = await session.execute(select(User).where(User.id == settler.user_id))
                    user = result.scalars().first()
                    result = await session.execute(select(Settlement).where(Settlement.id == settler.settlement_id))
                    settlement = result.scalars().first()
                    mention = f"<a href='tg://user?id={user.telegram_id}'>{user.name}</a>"
                    await bot.send_message(
                        settlement.chat_id,
                        f"⏰ <b>{mention}, не забудь выполнить лишнюю меру!</b> ({settler.quote}/{settler.target_quote})"
                    )
                except Exception as e:
                    log.error(f"Ошибка при отправке напоминания поселенцу {settler.id}: {e}")
        
        log.info("✅ Проверка поселенцев на переработку завершена.")

async def day_reset():
    async with SessionLocal() as session:
        log.info("↪️ Ежедневное обновление начато...")
        try:
            result = await session.execute(select(Settler))
            settlers = result.scalars().all()
        except Exception as e:
            log.error(f"Ошибка при получении поселенцев для ежедневного обновления: {e}")
            return
        
        try: # обновление квоты
            overtime_settlers = [s for s in settlers if s.overtime_is_toggled and not s.quote_is_completed]
            for settler in overtime_settlers:
                fine = 20 + settler.level
                await session.execute(
                    update(Settler)
                    .where(Settler.id == settler.id)
                    .values(balance=settler.balance - fine)
                )
                
                user_result = await session.execute(
                    select(User).where(User.id == settler.user_id)
                )
                user = user_result.scalars().first()
                if user:
                    mention = f"<a href='tg://user?id={user.telegram_id}'>{user.name}</a>"
                    settlement_result = await session.execute(
                        select(Settlement).where(Settlement.id == settler.settlement_id)
                    )
                    settlement = settlement_result.scalars().first()
                    if settlement:
                        await bot.send_message(settlement.chat_id, f"⚠️ <b>{mention} не поспел(а) свершить лишнюю меру!</b> Вира наложена: 💰 <b>{fine}</b>. Впредь будь расторопнее!")
            
            await session.execute(
                update(Settler)
                .values(
                    quote=0,
                    quote_is_completed=False,
                    overtime_count=0,
                    overtime_is_toggled=False
                )
            )
            
            for settler in settlers:
                await session.execute(
                    update(Settler)
                    .where(Settler.id == settler.id)
                    .values(
                        target_quote=round(settler.level * 0.85 + 6),
                        balance=settler.balance + settler.income
                    )
                )
        except Exception as e:
            log.error(f"Ошибка при ежедневном обновлении: {e}")
            return
        
        await session.commit()
        log.info(f"✅ Ежедневное обновление выполнено для {len(settlers)} поселенцев")