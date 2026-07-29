# Anime Finder Telegram bot

## Ishga tushirish

```bash
cd /home/sanjar
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

`.env` ichida `BOT_TOKEN`, `CHANNEL_ID` va vergul bilan `ADMIN_IDS` ni to‘ldiring. Bot kanalga administrator bo‘lishi va kanal postlarini ko‘rish huquqiga ega bo‘lishi kerak.

Bot API eski kanal tarixini o‘qish endpointiga ega emas. Shu sabab bot qo‘shilganidan keyingi video/document channel postlar keshga yoziladi. Eski kontentni indekslash uchun postlarni botga qayta yuborish yoki alohida Telegram user-client (MTProto) importer kerak.

Admin botga `/add` yuborib, keyin video yoki documentni caption bilan jo‘natsa, bot uni kanalga yuboradi va qidiruv cache’iga qo‘shadi. Caption ichida anime nomi va qism raqamini yozish tavsiya qilinadi.

Server-side boundary: token faqat `config.py` orqali server muhitidan olinadi; client Telegram bilan faqat Bot API orqali gaplashadi, kanal va SQLite ma’lumotlariga client to‘g‘ridan-to‘g‘ri kira olmaydi.

## Tekshirish va sozlash

`python -m compileall bot` sintaksis tekshiradi. Testda `cache_channel_message`, `Database.search`, pagination va admin authorization holatlarini mock Telegram obyektlari bilan tekshiring. Model/prompt/image sozlamalari bu loyihaga tegishli emas; qidiruv querysi `handlers/search.py`, cache intervali `main.py` dagi `minutes=30`, fayl turi esa `utils/cache.py` da o‘zgartiriladi.

Production’da systemd/Docker bilan doimiy ishga tushiring, `.env` ni commit qilmang va SQLite backup qiling.
# Anime-bot
