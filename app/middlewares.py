from aiogram import BaseMiddleware, types
from certifi import core
from app.config import setup_logging
import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable

log = setup_logging(logging.getLogger(__name__))

# === КАСТОМНЫЕ ОШИБКИ ===
class BaseBotError(Exception):
    #* Базовая ошибка бота.
    def __init__(self, log_message: str, user_message: str = "❌ Произошла внутренняя ошибка. Попробуйте позже. Если ошибка повторяется, обратитесь к <a href=\"https://t.me/megatocha\">создателю.</a>"):
        super().__init__(log_message)
        self.user_message = user_message

class GroupOwnerError(BaseBotError):
    #* Ошибка при получении создателя группы.
    def __init__(self, log_message: str, chat_id: int):
        super().__init__(log_message, user_message="❌ Произошла ошибка при получении данных создателя. Возможно, у бота нет прав администратора?")
        self.chat_id = chat_id

class UserCreationError(BaseBotError):
    #* Ошибка при создании/получении пользователя.
    def __init__(self, log_message: str, telegram_user_id: int):
        super().__init__(log_message, user_message="❌ Произошла ошибка при получении данных пользователя. Попробуйте позже.")
        self.telegram_user_id = telegram_user_id

class SettlementCreationError(BaseBotError):
    #* Ошибка при создании/получении поселения.
    def __init__(self, log_message: str, chat_id: int):
        super().__init__(log_message, user_message="❌ Произошла ошибка при получении данных группы. Попробуйте позже.")
        self.chat_id = chat_id

class SettlerCreationError(BaseBotError):
    #* Ошибка при создании/получении жителя.
    def __init__(self, log_message: str, user_id: int):
        super().__init__(log_message, user_message="❌ Произошла ошибка при получении данных пользователя. Попробуйте позже.")
        self.user_id = user_id


class ErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except GroupOwnerError as e:
            log.warning(f"{e.chat_id} | {str(e)}")
            if isinstance(event, types.Message):
                await event.answer(e.user_message)
            elif isinstance(event, types.CallbackQuery):
                await event.message.answer(e.user_message)
            return
        except (UserCreationError, SettlerCreationError, SettlementCreationError) as e:
            chat_id = getattr(event, 'chat', None)
            chat_id = chat_id.id if chat_id else 'unknown'
            log.error(f"{chat_id} | {str(e)} | user_id={getattr(e, 'telegram_user_id', 'unknown')}")
            if isinstance(event, types.Message):
                await event.answer(e.user_message)
            elif isinstance(event, types.CallbackQuery):
                await event.message.answer(e.user_message)
            return
        except BaseBotError as e:
            chat_id = getattr(event, 'chat', None)
            chat_id = chat_id.id if chat_id else 'unknown'
            log.error(f"{chat_id} | {str(e)}")
            if isinstance(event, types.Message):
                await event.answer(e.user_message)
            elif isinstance(event, types.CallbackQuery):
                await event.message.answer(e.user_message)
            return
        except Exception as e:
            error_msg = str(e).lower()
            chat_id = getattr(event, 'chat', None)
            chat_id = chat_id.id if chat_id else 'unknown'
            
            if any(phrase in error_msg for phrase in [
                "message is not modified",
                "too many requests",
                "retry after",
                "flood control exceeded"
            ]):
                log.debug(f"{chat_id} | Некритичная ошибка: {str(e)}")
                return
            
            log.critical(f"{chat_id} | Неизвестная ошибка: {str(e)}")
            if isinstance(event, types.Message):
                await event.answer('❌ Неизвестная ошибка. Обратитесь к <a href="https://t.me/megatocha">создателю.</a>')
            elif isinstance(event, types.CallbackQuery):
                await event.message.answer('❌ Неизвестная ошибка. Обратитесь к <a href="https://t.me/megatocha">создателю.</a>')
            raise e



class UserMiddleware(BaseMiddleware):
    def __init__(self, user_getOrCreate: Callable):
        self.user_getOrCreate = user_getOrCreate
    
    async def __call__(self, handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: Dict[str, Any]) -> Any:
        tg_user = data.get("event_from_user")
        
        if tg_user:
            user = await self.user_getOrCreate(tg_user)
            data["user"] = user
            
        return await handler(event, data)