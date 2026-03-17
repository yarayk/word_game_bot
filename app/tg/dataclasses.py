from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MessageFrom:
    id: int
    first_name: str
    username: str | None = None
    is_bot: bool = False


@dataclass
class Chat:
    id: int
    type: str


@dataclass
class Message:
    message_id: int
    from_: MessageFrom
    chat: Chat
    text: str | None = None
    new_chat_members: list[MessageFrom] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        return cls(
            message_id=data["message_id"],
            from_=MessageFrom(
                id=data["from"]["id"],
                first_name=data["from"]["first_name"],
                username=data["from"].get("username"),
                is_bot=data["from"].get("is_bot", False),
            ),
            chat=Chat(
                id=data["chat"]["id"],
                type=data["chat"]["type"],
            ),
            text=data.get("text"),
            new_chat_members=[
                MessageFrom(
                    id=m["id"],
                    first_name=m["first_name"],
                    username=m.get("username"),
                    is_bot=m.get("is_bot", False),
                )
                for m in data.get("new_chat_members", [])
            ],
        )


@dataclass
class CallbackQuery:
    id: str
    from_: MessageFrom
    message: Message
    data: str

    @classmethod
    def from_dict(cls, raw: dict) -> CallbackQuery:
        return cls(
            id=raw["id"],
            from_=MessageFrom(
                id=raw["from"]["id"],
                first_name=raw["from"]["first_name"],
                username=raw["from"].get("username"),
                is_bot=raw["from"].get("is_bot", False),
            ),
            message=Message.from_dict(raw["message"]),
            data=raw.get("data", ""),
        )


@dataclass
class Update:
    update_id: int
    message: Message | None = None
    callback_query: CallbackQuery | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Update:
        return cls(
            update_id=data["update_id"],
            message=(
                Message.from_dict(data["message"])
                if "message" in data
                else None
            ),
            callback_query=(
                CallbackQuery.from_dict(data["callback_query"])
                if "callback_query" in data
                else None
            ),
        )
