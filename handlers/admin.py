import re
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.event.bases import SkipHandler
try:
    from .search import code_search_users
except ImportError:
    from handlers.search import code_search_users
try:
    from ..database import Database
    from ..utils.cache import cache_channel_message
except ImportError:
    from database import Database
    from utils.cache import cache_channel_message

router = Router()
pending_trailers: dict[int, int] = {}
pending_episodes: dict[int, dict] = {}
pending_animes: dict[int, dict] = {}
pending_required_channels: set[int] = set()

def is_admin(message, settings):
    return message.from_user.id in settings.admin_ids

async def db_save_and_publish(message: Message, bot: Bot, db: Database, settings, code: int, name: str, trailer: str, voice: str = "", genre: str = "", language: str = "Uzbek tilida"):
    caption = f"🎬 <b>{name}</b>\n\n🎤 Ovoz berdi: {voice or '—'}\n📂 Nomi: {name}\n📝 Qismlar: 0 ta\n🎭 Janri: {genre or '—'}\n🌐 Tili: {language or 'Uzbek tilida'}\n🆔 Anime kodi: {code}"
    sent = await bot.send_video(settings.channel_id, trailer, caption=caption, parse_mode="HTML")
    await db.save_anime(code, name, trailer, sent.message_id)
    await db.save_trailer(code, trailer, message.from_user.id)
    await bot.edit_message_reply_markup(chat_id=settings.channel_id, message_id=sent.message_id, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Yuklab olish", url=f"https://t.me/tarjimaanimelaruz_bot?start=anime_{code}")]
    ]))
    await message.answer(f"✅ {name} anime sifatida kanalga qo‘shildi.")

@router.message(Command("addtrailer"))
async def addtrailer(message: Message, settings):
    if not is_admin(message, settings): return
    await message.answer("🎬 Anime kodini yuboring (masalan: 26). Keyin trailer videosini yuborasiz.")

@router.message(Command("addepisode"))
async def addepisode(message: Message, settings):
    if not is_admin(message, settings): return
    pending_episodes[message.from_user.id] = {"step": "name"}
    await message.answer("🎞 1/4 Anime nomini yuboring:")

@router.message(Command("addanime"))
async def addanime(message: Message, settings):
    if not is_admin(message, settings): return
    pending_animes[message.from_user.id] = {"step": "trailer"}
    await message.answer("🎬 1/3 Avval anime trailer videosini yuboring:")

@router.message(F.text, ~F.text.startswith("/"))
async def episode_details(message: Message, bot: Bot, db: Database, settings):
    if not is_admin(message, settings): return
    if message.from_user.id in pending_required_channels:
        pending_required_channels.remove(message.from_user.id)
        try:
            channel_ref, _, invite_link = message.text.partition("|")
            channel_ref = channel_ref.strip()
            try:
                chat = await bot.get_chat(channel_ref)
                channel_id, title, username = chat.id, (chat.title or chat.full_name), (chat.username or "")
            except Exception:
                if not channel_ref.lstrip("-").isdigit():
                    raise
                channel_id, title, username = int(channel_ref), f"Yopiq kanal {channel_ref}", ""
            await db.save_required_channel(channel_id, title, username, invite_link.strip())
            return await message.answer(f"✅ Majburiy kanal qo‘shildi: {title}")
        except Exception:
            return await message.answer("⚠️ Kanal topilmadi. @username yoki kanal ID yuboring.")
    state = pending_episodes.get(message.from_user.id)
    anime_state = pending_animes.get(message.from_user.id)
    if anime_state:
        if anime_state["step"] == "edit_name":
            await db.save_anime(anime_state["code"], message.text.strip())
            pending_animes.pop(message.from_user.id, None)
            return await message.answer("✅ Anime nomi tahrirlandi.")
        if anime_state["step"] == "name":
            anime_state.update(name=message.text.strip(), step="voice")
            return await message.answer("✅ Ovoz bergan aktyor/dublyaj nomini yuboring:")
        if anime_state["step"] == "voice":
            anime_state.update(voice=message.text.strip(), step="genre")
            return await message.answer("✅ Janrini yuboring:")
        if anime_state["step"] == "genre":
            anime_state.update(genre=message.text.strip(), step="language")
            return await message.answer("✅ Tilini yuboring (masalan: Uzbek tilida):")
        if anime_state["step"] == "language":
            anime_state.update(language=message.text.strip(), step="code")
            return await message.answer("✅ Anime kodini yuboring (faqat raqam):")
        if anime_state["step"] == "code" and message.text.strip().isdigit():
            code = int(message.text.strip())
            name = anime_state["name"]
            pending_animes.pop(message.from_user.id, None)
            await db_save_and_publish(message, bot, db, settings, code, name, anime_state["trailer"], anime_state.get("voice", ""), anime_state.get("genre", ""), anime_state.get("language", "Uzbek tilida"))
            return
        return
    if not state: raise SkipHandler
    if state["step"] == "name":
        state.update(name=message.text.strip(), step="code")
        return await message.answer("✅ 2/4 Anime kodi (faqat raqam)ni yuboring:")
    if state["step"] == "code" and message.text.strip().isdigit():
        state.update(code=int(message.text.strip()), step="episode")
        return await message.answer("✅ 3/4 Qism raqamini yuboring:")
    if state["step"] == "episode":
        episode_match = re.search(r"(?:qism|episode|ep)?\s*[-:#]?\s*(\d+)", message.text.strip(), re.I)
        if not episode_match:
            return await message.answer("⚠️ Qism raqamini yuboring. Masalan: <code>1</code> yoki <code>1-qism</code>.", parse_mode="HTML")
        state.update(episode=int(episode_match.group(1)), step="video")
        return await message.answer("✅ 4/4 Endi qism videosini yuboring:")

@router.message(F.text.regexp(r"^\d+$"))
async def trailer_code(message: Message, settings):
    if message.from_user.id in code_search_users:
        raise SkipHandler
    if is_admin(message, settings):
        pending_trailers[message.from_user.id] = int(message.text)
        await message.answer(f"✅ {message.text} kodi qabul qilindi. Endi trailer videosini yuboring: /cancel")

@router.message(F.video)
async def add_video(message: Message, bot: Bot, db: Database, settings):
    if not is_admin(message, settings): return
    try:
        anime_state = pending_animes.get(message.from_user.id)
        if anime_state and anime_state["step"] == "trailer":
            anime_state.update(trailer=message.video.file_id, step="name")
            return await message.answer("✅ 2/3 Anime nomini yuboring:")
        episode_details_value = pending_episodes.get(message.from_user.id)
        if episode_details_value and episode_details_value["step"] != "video":
            return await message.answer("⚠️ Avval bot so‘ragan ma’lumotni yuboring. Hozir qism raqami kutilmoqda.")
        if episode_details_value and episode_details_value["step"] == "video":
            pending_episodes.pop(message.from_user.id, None)
            code, name, episode = episode_details_value["code"], episode_details_value["name"], episode_details_value["episode"]
            if episode_details_value.get("code") and episode_details_value.get("name"):
                episode_caption = (
                    f"🎬 <b>{episode_details_value['name']}</b>\n\n"
                    f"📌 Nomi: {episode_details_value['name']}\n"
                    f"🔢 Qism: {episode_details_value['episode']}\n"
                    f"🆔 Anime kodi: {episode_details_value['code']}"
                )
            else:
                episode_caption = (
                f"🎬 <b>{name}</b>\n\n"
                f"📌 Nomi: {name}\n"
                f"🔢 Qism: {episode}\n"
                f"🆔 Anime kodi: {code}\n\n"
                f"⬇️ Qismni yuklab olish uchun tugmani bosing"
                )
            await db.save_message(-message.message_id, f"kod:{code} {name} qism:{episode}", message.video.file_id, "video", message.date.isoformat())
            anime = await db.get_anime(code)
            if anime and anime[3]:
                count = len(await db.get_episodes(code))
                details = await db.get_anime_details(code)
                voice, genre, language = (details[1:] if details else ("", "", "Uzbek tilida"))
                await bot.edit_message_caption(
                    chat_id=settings.channel_id,
                    message_id=anime[3],
                    caption=f"🎬 <b>{anime[1]}</b>\n\n🎤 Ovoz berdi: {voice or '—'}\n📂 Nomi: {anime[1]}\n📝 Qismlar: {count} ta\n🎭 Janri: {genre or '—'}\n🌐 Tili: {language or 'Uzbek tilida'}\n🆔 Anime kodi: {anime[0]}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📥 Yuklab olish", url=f"https://t.me/tarjimaanimelaruz_bot?start=anime_{anime[0]}")]
                    ])
                )
            return await message.answer(f"✅ {name} — {episode}-qism qo‘shildi va cache qilindi.")
        trailer_code_value = pending_trailers.pop(message.from_user.id, None)
        if trailer_code_value is not None:
            await db.save_trailer(trailer_code_value, message.video.file_id, message.from_user.id)
            return await message.answer(f"✅ {trailer_code_value}-anime uchun trailer saqlandi.")
        sent = await bot.send_video(settings.channel_id, message.video.file_id, caption=message.caption or "Video")
        await cache_channel_message(sent, db)
        await message.answer("✅ Video kanalga qo‘shildi va cache qilindi.")
    except Exception:
        await message.answer("⚠️ Video qo‘shishda xatolik yuz berdi.")

@router.message(Command("admin"))
async def admin(message: Message, db: Database, settings):
    if not is_admin(message, settings): return
    users, searches, messages = await db.stats()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Anime qo‘shish", callback_data="admin:addanime")], [InlineKeyboardButton(text="📚 Anime boshqarish", callback_data="admin:anime_list")], [InlineKeyboardButton(text="🔔 Eslatish", callback_data="admin:reminder")], [InlineKeyboardButton(text="🔒 Majburiy kanallar", callback_data="admin:required_channels")], [InlineKeyboardButton(text="🧹 Keshni tozalash", callback_data="admin:clear")], [InlineKeyboardButton(text="📣 Broadcast", callback_data="admin:broadcast")]])
    await message.answer(f"🛠 <b>Admin panel</b>\n\n👥 Foydalanuvchilar: {users}\n🔎 Qidiruvlar: {searches}\n🎞 Keshdagi xabarlar: {messages}\n\nAnime qo‘shish: /addanime", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "admin:addepisode")
async def add_episode_help(callback: CallbackQuery, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    await callback.answer()
    pending_episodes[callback.from_user.id] = {"step": "name"}
    await callback.message.answer("🎞 1/4 Anime nomini yuboring:")

@router.callback_query(F.data == "admin:addanime")
async def add_anime_help(callback: CallbackQuery, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    pending_animes[callback.from_user.id] = {"step": "trailer"}
    await callback.answer()
    await callback.message.answer("🎬 1/3 Avval anime trailer videosini yuboring:")

@router.callback_query(F.data == "admin:required_channels")
async def required_channels_menu(callback: CallbackQuery, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    rows = await db.required_channels()
    buttons = [[InlineKeyboardButton(text=f"🗑 {title}", callback_data=f"admin:req_delete:{channel_id}")] for channel_id, title, _, _ in rows]
    buttons.append([InlineKeyboardButton(text="➕ Kanal qo‘shish", callback_data="admin:req_add")])
    await callback.answer(); await callback.message.answer("🔒 Majburiy kanallar:\n\nKanalni o‘chirish uchun ustiga bosing.", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "admin:req_add")
async def required_channel_add(callback: CallbackQuery, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    pending_required_channels.add(callback.from_user.id)
    await callback.answer(); await callback.message.answer("Kanal @username yoki ID sini yuboring. Yopiq kanal uchun invite linkni ham qo‘shing:\n\n<code>-1001234567890 | https://t.me/+AbCdEf123</code>\n\nBot kanalga administrator bo‘lishi kerak.", parse_mode="HTML")

@router.callback_query(F.data.startswith("admin:req_delete:"))
async def required_channel_delete(callback: CallbackQuery, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    await db.delete_required_channel(int(callback.data.split(":")[2]))
    await callback.answer("Kanal o‘chirildi")
    await callback.message.edit_text("✅ Majburiy kanal o‘chirildi.")

@router.callback_query(F.data == "admin:reminder")
async def reminder_menu(callback: CallbackQuery, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    await callback.answer()
    await callback.message.answer("🔔 Eslatish bo‘limi:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga eslatish", callback_data="admin:remind_channel")],
        [InlineKeyboardButton(text="👥 Botdagi odamlarga eslatish", callback_data="admin:remind_users")]
    ]))

@router.callback_query(F.data == "admin:remind_channel")
async def remind_channel(callback: CallbackQuery, bot: Bot, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    animes = await db.list_animes()
    if not animes: return await callback.answer("Database’da anime yo‘q", show_alert=True)
    buttons = [[InlineKeyboardButton(text=f"🎬 {name[:35]} ({code})", callback_data=f"admin:remind_one:{code}")] for code, name, trailer, _ in animes if trailer]
    await callback.answer()
    await callback.message.answer("📢 Kanalga qayta yuborish uchun anime tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("admin:remind_one:"))
async def remind_one(callback: CallbackQuery, bot: Bot, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    code = int(callback.data.split(":")[2]); anime = await db.get_anime(code)
    if not anime or not anime[2]: return await callback.answer("Trailer topilmadi", show_alert=True)
    details = await db.get_anime_details(code)
    voice, genre, language = (details[1:] if details else ("", "", "Uzbek tilida"))
    count = len(await db.get_episodes(code))
    caption = f"🎬 <b>{anime[1]}</b>\n\n🎤 Ovoz berdi: {voice or '—'}\n📂 Nomi: {anime[1]}\n📝 Qismlar: {count} ta\n🎭 Janri: {genre or '—'}\n🌐 Tili: {language or 'Uzbek tilida'}\n🆔 Anime kodi: {code}"
    sent = await bot.send_video(settings.channel_id, anime[2], caption=caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Yuklab olish", url=f"https://t.me/tarjimaanimelaruz_bot?start=anime_{code}")]
    ]))
    await db.save_anime(code, anime[1], anime[2], sent.message_id, voice, genre, language)
    await callback.answer("Kanalga yuborildi")
    await callback.message.answer(f"✅ {anime[1]} kanalda eslatildi.")

@router.callback_query(F.data == "admin:remind_users")
async def remind_users(callback: CallbackQuery, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    await callback.answer()
    await callback.message.answer("👥 Botdagi foydalanuvchilarga xabar yuborish uchun:\n\n/broadcast Xabaringizni shu yerga yozing")

@router.callback_query(F.data == "admin:anime_list")
async def anime_list(callback: CallbackQuery, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    animes = await db.list_animes()
    if not animes: return await callback.answer("Hali anime qo‘shilmagan", show_alert=True)
    buttons = [[InlineKeyboardButton(text=f"🎞 {name[:35]} ({code})", callback_data=f"admin:anime:{code}")] for code, name, _, _ in animes]
    await callback.answer()
    await callback.message.answer("📚 Anime tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("admin:anime:"))
async def anime_manage(callback: CallbackQuery, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    code = int(callback.data.split(":")[2])
    rows = await db.get_episodes(code)
    await callback.answer()
    await callback.message.answer(f"🎞 {await db.get_anime(code) or code}\n📦 Qismlar: {len(rows)}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qism qo‘shish", callback_data=f"admin:addpart:{code}" )],
        [InlineKeyboardButton(text="✏️ Nomini tahrirlash", callback_data=f"admin:edit:{code}"), InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"admin:delete:{code}")]
    ]))

@router.callback_query(F.data.startswith("admin:addpart:"))
async def add_part(callback: CallbackQuery, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    code = int(callback.data.split(":")[2]); anime = await db.get_anime(code)
    pending_episodes[callback.from_user.id] = {"step": "episode", "code": code, "name": anime[1] if anime else str(code)}
    await callback.answer(); await callback.message.answer("Qism raqamini yuboring, keyin videosini yuboring:")

@router.callback_query(F.data.startswith("admin:delete:"))
async def delete_anime(callback: CallbackQuery, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    code = int(callback.data.split(":")[2]); await db.delete_anime(code); await callback.answer("Anime o‘chirildi"); await callback.message.edit_text("✅ Anime va uning ma’lumotlari o‘chirildi.")

@router.callback_query(F.data.startswith("admin:edit:"))
async def edit_anime(callback: CallbackQuery, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    code = int(callback.data.split(":")[2]); anime = await db.get_anime(code)
    if not anime: return await callback.answer("Anime topilmadi", show_alert=True)
    pending_animes[callback.from_user.id] = {"step": "edit_name", "code": code}
    await callback.answer(); await callback.message.answer(f"Hozirgi nom: {anime[1]}\nYangi nomni yuboring:")

@router.callback_query(F.data == "admin:addtrailer")
async def add_trailer_help(callback: CallbackQuery, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    await callback.answer()
    await callback.message.answer("Foydalanish: /addtrailer buyrug‘ini yuboring, keyin anime kodini va trailer videosini yuboring.")

@router.callback_query(F.data == "admin:clear")
async def clear(callback: CallbackQuery, db: Database, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    await db.clear_messages(); await callback.answer("Kesh tozalandi")
    await callback.message.answer("✅ Kesh tozalandi.")

@router.callback_query(F.data == "admin:broadcast")
async def broadcast_help(callback: CallbackQuery, settings):
    if callback.from_user.id not in settings.admin_ids: return await callback.answer("Ruxsat yo‘q", show_alert=True)
    await callback.answer(); await callback.message.answer("Foydalanish: /broadcast Sizning xabaringiz")

@router.message(Command("broadcast"))
async def broadcast(message: Message, bot: Bot, db: Database, settings):
    if not is_admin(message, settings): return
    text = message.text.partition(" ")[2].strip()
    if not text: return await message.answer("Foydalanish: /broadcast Sizning xabaringiz")
    sent = 0
    for user_id in await db.user_ids():
        try: await bot.send_message(user_id, text); sent += 1
        except Exception: pass
    await message.answer(f"✅ Broadcast {sent} ta foydalanuvchiga yuborildi.")
