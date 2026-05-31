from __future__ import annotations

from datetime import datetime, timezone

from aiogram import types


def _dump(model):
    return model.model_dump(by_alias=True, exclude_none=True)


def build_user(
    user_id: int = 1,
    first_name: str = "Tester",
    language_code: str = "ru",
    is_bot: bool = False,
):
    return types.User.model_validate(
        {
            "id": user_id,
            "is_bot": is_bot,
            "first_name": first_name,
            "language_code": language_code,
        }
    )


def build_chat(
    chat_id: int = -1001,
    chat_type: str = "supergroup",
    title: str = "Test chat",
):
    payload = {
        "id": chat_id,
        "type": chat_type,
    }
    if title is not None:
        payload["title"] = title
    return types.Chat.model_validate(payload)


def build_message(
    text: str | None = "hello",
    *,
    from_user: types.User | None = None,
    chat: types.Chat | None = None,
    message_id: int = 1,
    reply_to_message: types.Message | None = None,
    location: dict | None = None,
):
    from_user = from_user or build_user()
    chat = chat or build_chat()

    payload = {
        "message_id": message_id,
        "date": datetime.now(timezone.utc),
        "chat": _dump(chat),
        "from": _dump(from_user),
    }
    if text is not None:
        payload["text"] = text
    if reply_to_message is not None:
        payload["reply_to_message"] = _dump(reply_to_message)
    if location is not None:
        payload["location"] = location

    return types.Message.model_validate(payload)


def build_callback_query(
    data: str = "callback:data",
    *,
    from_user: types.User | None = None,
    message: types.Message | None = None,
    callback_id: str = "callback-id",
):
    from_user = from_user or build_user()
    message = message or build_message(from_user=from_user)
    return types.CallbackQuery.model_validate(
        {
            "id": callback_id,
            "from": _dump(from_user),
            "chat_instance": "chat-instance",
            "data": data,
            "message": _dump(message),
        }
    )


def build_chat_member_updated(
    *,
    chat: types.Chat | None = None,
    from_user: types.User | None = None,
    old_status: str = "left",
    new_status: str = "member",
):
    chat = chat or build_chat()
    from_user = from_user or build_user()
    return types.ChatMemberUpdated.model_validate(
        {
            "chat": _dump(chat),
            "from": _dump(from_user),
            "date": datetime.now(timezone.utc),
            "old_chat_member": {
                "status": old_status,
                "user": _dump(from_user),
            },
            "new_chat_member": {
                "status": new_status,
                "user": _dump(from_user),
            },
        }
    )
