from datetime import datetime, timezone
from pathlib import Path
import aiosqlite


class Database:
    def __init__(self, path: str = "bot.db"):
        database_path = Path(path)
        self.path = database_path if database_path.is_absolute() else Path(__file__).resolve().parent / database_path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, created_at TEXT, search_count INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS messages (message_id INTEGER PRIMARY KEY, caption TEXT, file_id TEXT, file_type TEXT, date TEXT, cached_at TEXT);
            CREATE TABLE IF NOT EXISTS searches (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, query TEXT, results_count INTEGER, created_at TEXT);
            CREATE TABLE IF NOT EXISTS trailers (anime_code INTEGER PRIMARY KEY, file_id TEXT NOT NULL, added_by INTEGER NOT NULL, added_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS animes (anime_code INTEGER PRIMARY KEY, name TEXT NOT NULL, trailer_file_id TEXT, channel_message_id INTEGER, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS required_channels (channel_id INTEGER PRIMARY KEY, title TEXT NOT NULL, username TEXT);
            """)
            for column in ("voice TEXT", "genre TEXT", "language TEXT"):
                try:
                    await db.execute(f"ALTER TABLE animes ADD COLUMN {column}")
                except Exception:
                    pass
            try:
                await db.execute("ALTER TABLE required_channels ADD COLUMN invite_link TEXT")
            except Exception:
                pass
            await db.commit()

    async def save_anime(self, code: int, name: str, trailer_file_id: str = None, channel_message_id: int = None, voice: str = "", genre: str = "", language: str = "Uzbek tilida"):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO animes(anime_code, name, trailer_file_id, channel_message_id, created_at, voice, genre, language) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(anime_code) DO UPDATE SET name=excluded.name, trailer_file_id=COALESCE(excluded.trailer_file_id, animes.trailer_file_id), channel_message_id=COALESCE(excluded.channel_message_id, animes.channel_message_id), voice=excluded.voice, genre=excluded.genre, language=excluded.language", (code, name, trailer_file_id, channel_message_id, datetime.now(timezone.utc).isoformat(), voice, genre, language))
            await db.commit()

    async def get_anime_details(self, code: int):
        async with aiosqlite.connect(self.path) as db:
            return await (await db.execute("SELECT name, voice, genre, language FROM animes WHERE anime_code=?", (code,))).fetchone()

    async def save_required_channel(self, channel_id: int, title: str, username: str = "", invite_link: str = ""):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR REPLACE INTO required_channels(channel_id, title, username, invite_link) VALUES (?, ?, ?, ?)", (channel_id, title, username, invite_link))
            await db.commit()

    async def required_channels(self):
        async with aiosqlite.connect(self.path) as db:
            return await (await db.execute("SELECT channel_id, title, username, invite_link FROM required_channels ORDER BY title")).fetchall()

    async def delete_required_channel(self, channel_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM required_channels WHERE channel_id=?", (channel_id,))
            await db.commit()

    async def get_anime(self, code: int):
        async with aiosqlite.connect(self.path) as db:
            return await (await db.execute("SELECT anime_code, name, trailer_file_id, channel_message_id FROM animes WHERE anime_code=?", (code,))).fetchone()

    async def list_animes(self):
        async with aiosqlite.connect(self.path) as db:
            return await (await db.execute("SELECT anime_code, name, trailer_file_id, channel_message_id FROM animes ORDER BY name COLLATE NOCASE")).fetchall()

    async def delete_anime(self, code: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM animes WHERE anime_code=?", (code,))
            await db.execute("DELETE FROM trailers WHERE anime_code=?", (code,))
            await db.execute("DELETE FROM messages WHERE caption LIKE ? OR caption LIKE ?", (f"%kod:{code}%", f"%#{code}%"))
            await db.commit()

    async def upsert_user(self, user):
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO users VALUES (?, ?, ?, ?, 0) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name", (user.id, user.username, user.first_name, now))
            await db.commit()

    async def save_message(self, message_id, caption, file_id, file_type, date):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR REPLACE INTO messages VALUES (?, ?, ?, ?, ?, ?)", (message_id, caption or "", file_id, file_type, date, datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def search(self, user_id: int, query: str):
        pattern = f"%{query.lower()}%"
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT message_id, caption, file_id, file_type FROM messages WHERE lower(caption) LIKE ? ORDER BY date DESC", (pattern,))
            rows = await cursor.fetchall()
            await db.execute("INSERT INTO searches(user_id, query, results_count, created_at) VALUES (?, ?, ?, ?)", (user_id, query, len(rows), datetime.now(timezone.utc).isoformat()))
            await db.execute("UPDATE users SET search_count=search_count+1 WHERE user_id=?", (user_id,))
            await db.commit()
            return rows

    async def get_episodes(self, anime_code: int):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT message_id, caption, file_id, file_type FROM messages WHERE caption LIKE ? OR caption LIKE ? ORDER BY date ASC", (f"%kod:{anime_code}%", f"%#{anime_code}%"))
            return await cursor.fetchall()

    async def get_message(self, message_id: int):
        async with aiosqlite.connect(self.path) as db:
            return await (await db.execute("SELECT caption, file_id, file_type FROM messages WHERE message_id=?", (message_id,))).fetchone()

    async def save_trailer(self, anime_code: int, file_id: str, added_by: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR REPLACE INTO trailers VALUES (?, ?, ?, ?)", (anime_code, file_id, added_by, datetime.now(timezone.utc).isoformat()))
            await db.commit()

    async def get_trailer(self, anime_code: int):
        async with aiosqlite.connect(self.path) as db:
            return await (await db.execute("SELECT file_id FROM trailers WHERE anime_code=?", (anime_code,))).fetchone()

    async def stats(self):
        async with aiosqlite.connect(self.path) as db:
            users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
            searches = (await (await db.execute("SELECT COUNT(*) FROM searches")).fetchone())[0]
            messages = (await (await db.execute("SELECT COUNT(*) FROM messages")).fetchone())[0]
            return users, searches, messages

    async def user_ids(self):
        async with aiosqlite.connect(self.path) as db:
            return [row[0] for row in await (await db.execute("SELECT user_id FROM users")).fetchall()]

    async def clear_messages(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM messages")
            await db.commit()
