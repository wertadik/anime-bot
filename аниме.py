import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
import aiohttp

TOKEN = "7556682563:AAHrBsND0a5c2pkl69iMaE-4yPtFVkUrnaE"
MAX_ANIME = 55
SHIKIMORI_URL = "https://shikimori.one/api"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
router = Router()

MONTH_NAMES = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

STATUS_TRANSLATION = {
    "released": "✅ Завершено",
    "ongoing": "🟡 Выходит",
    "anons": "🔵 Анонсировано"
}

async def get_seasons(anime_id: int) -> list:
    """Получение информации о всех сезонах"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{SHIKIMORI_URL}/animes/{anime_id}/related",
                headers={"User-Agent": "AnimeSeasonsBot/3.0"}
            ) as response:
                related = await response.json()
                seasons = []
                
                # Собираем все сиквелы
                for item in related:
                    if item["relation"] == "sequel" and item["anime"]:
                        seasons.append(item["anime"])
                
                # Добавляем оригинальный сезон
                async with session.get(
                    f"{SHIKIMORI_URL}/animes/{anime_id}",
                    headers={"User-Agent": "AnimeSeasonsBot/3.0"}
                ) as resp:
                    main = await resp.json()
                    seasons.insert(0, main)
                
                return sorted(seasons, key=lambda x: x.get('aired_on', '9999-99-99'))
    except Exception as e:
        logger.error(f"Seasons error: {str(e)}")
        return []

def format_date(date_str: str) -> str:
    """Форматирование даты на русском"""
    try:
        year, month, day = map(int, date_str.split('-'))
        return f"{day} {MONTH_NAMES.get(month, '???')} {year}"
    except:
        return "Дата неизвестна"

def format_season(season: dict) -> str:
    """Форматирование информации о сезоне"""
    name = season.get('russian') or season.get('name', 'Без названия')
    episodes = season.get('episodes', '?')
    status = STATUS_TRANSLATION.get(season.get('status'), "⚪ Неизвестно")
    
    dates = []
    if aired_on := season.get('aired_on'):
        dates.append(f"▶️ Начало: {format_date(aired_on)}")
    if released_on := season.get('released_on'):
        dates.append(f"⏹️ Конец: {format_date(released_on)}")
    
    return (
        f"🌐 {name}\n"
        f"┣ {status}\n"
        f"┣ Эпизодов: {episodes}\n"
        f"┗ {' | '.join(dates) if dates else '📅 Даты неизвестны'}"
    )

async def process_anime(title: str) -> str:
    """Обработка одного аниме"""
    try:
        async with aiohttp.ClientSession() as session:
            # Поиск основного аниме
            async with session.get(
                f"{SHIKIMORI_URL}/animes",
                params={"search": title, "limit": 1},
                headers={"User-Agent": "AnimeSeasonsBot/3.0"}
            ) as resp:
                data = await resp.json()
                if not data:
                    return f"❌ {title} - не найдено"
                
                main = data[0]
                seasons = await get_seasons(main['id'])
                
                result = [f"🎌 **{main.get('russian', main['name'])}**"]
                for i, season in enumerate(seasons, 1):
                    result.append(f"\n📀 Сезон {i}\n{format_season(season)}")
                
                return '\n'.join(result)
                
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return f"⚠️ Ошибка обработки: {title}"

@router.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "🔍 Отправьте список аниме (через запятую или с новой строки)\n"
        "Пример:\n"
        "Атака титанов, Магическая битва\n"
        "Человек-бензопила"
    )

@router.message(F.text)
async def handle_message(message: types.Message):
    anime_list = re.split(r'[\n,;]+', message.text)
    anime_list = [t.strip() for t in anime_list if t.strip()][:MAX_ANIME]
    
    if not anime_list:
        return await message.answer("❌ Список аниме пуст")
    
    progress_msg = await message.answer(f"⏳ Начинаю обработку {len(anime_list)} аниме...")
    
    results = []
    for idx, title in enumerate(anime_list, 1):
        try:
            result = await process_anime(title)
            results.append(f"{idx}. {result}")
            
            if idx % 5 == 0:
                await progress_msg.edit_text(f"⏳ Обработано: {idx}/{len(anime_list)}")
                
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error processing {title}: {str(e)}")
            results.append(f"{idx}. ❌ Ошибка: {title}")
    
    # Отправка частями
    full_report = "\n\n".join(results)
    parts = [full_report[i:i+4096] for i in range(0, len(full_report), 4096)]
    
    for part in parts:
        await message.answer(part)
    
    await progress_msg.delete()

async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())