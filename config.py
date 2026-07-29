import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _admin_ids() -> set[int]:
    return {int(value.strip()) for value in os.getenv("ADMIN_IDS", "").split(",") if value.strip()}


@dataclass(frozen=True)
class Settings:
    bot_token: str
    channel_id: int
    admin_ids: set[int]
    database_path: str = "bot.db"


def get_settings() -> Settings:
    token = os.getenv("BOT_TOKEN")
    channel = os.getenv("CHANNEL_ID")
    if not token or not channel:
        raise RuntimeError("BOT_TOKEN va CHANNEL_ID environment variablelari kerak")
    return Settings(token, int(channel), _admin_ids())
