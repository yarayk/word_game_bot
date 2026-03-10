from dataclasses import dataclass


@dataclass
class MessageFrom:
    id: int
    first_name: str
    username: str | None = None


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

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            message_id=data["message_id"],
            from_=MessageFrom(
                id=data["from"]["id"],
                first_name=data["from"]["first_name"],
                username=data["from"].get("username"),
            ),
            chat=Chat(
                id=data["chat"]["id"],
                type=data["chat"]["type"],
            ),
            text=data.get("text"),
        )


@dataclass
class Update:
    update_id: int
    message: Message | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Update":
        return cls(
            update_id=data["update_id"],
            message=(
                Message.from_dict(data["message"])
                if "message" in data
                else None
            ),
        )
