import os
import asyncio
import logging
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from map_generator import generate_map_image

load_dotenv()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

async def scrape_dexerto():
    url = "https://www.dexerto.com/gta/gta-online-gun-van-location-railgun-weapons-more-2031074/"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for p in soup.select("article p, .article-body p"):
            text = p.get_text(strip=True)
            if "gun van" in text.lower() and ("found" in text.lower() or "located" in text.lower() or "spawn" in text.lower()):
                return {"location": text, "image_url": None, "source": "Dexerto"}
    except Exception as e:
        logger.warning(f"Dexerto failed: {e}")
    return None

async def scrape_gtaboom():
    url = "https://www.gtaboom.com/gun-van-location-today-updated-daily-find-the-gun-van-and-railgun-ef55"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for p in soup.select("p, .entry-content p"):
            text = p.get_text(strip=True)
            if ("gun van" in text.lower() or "location" in text.lower()) and len(text) > 30:
                return {"location": text, "image_url": None, "source": "GTABoom"}
    except Exception as e:
        logger.warning(f"GTABoom failed: {e}")
    return None

async def scrape_holdtoreset():
    url = "https://holdtoreset.com/gta-online-daily-reset-tracker/"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for p in soup.select("p"):
            text = p.get_text(strip=True)
            if "gun van" in text.lower() and len(text) > 20:
                return {"location": text, "image_url": None, "source": "HoldToReset"}
    except Exception as e:
        logger.warning(f"HoldToReset failed: {e}")
    return None

async def get_gun_van_info():
    for scraper in [scrape_dexerto, scrape_gtaboom, scrape_holdtoreset]:
        result = await scraper()
        if result and result.get("location"):
            return result
    return {"location": "Could not fetch today's location. Check: https://www.dexerto.com/gta/gta-online-gun-van-location-railgun-weapons-more-2031074/", "image_url": None, "source": "Fallback"}

def build_message(info):
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    return (
        f"🚐 *GTA Online — Gun Van Location*\n"
        f"📅 *{today}*\n\n"
        f"{info['location']}\n\n"
        f"🗺️ [Interactive Map](https://gtaweb.eu/gtao-map/ls/2)\n\n"
        f"⏰ Resets daily at *4:00 PM AEST*\n"
        f"_Source: {info['source']}_"
    )

async def send_daily_update():
    logger.info("Fetching Gun Van location...")
    info = await get_gun_van_info()
    message = build_message(info)
    bot = Bot(token=BOT_TOKEN)
    map_buf = await generate_map_image(info["location"])
    try:
        if map_buf:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=map_buf, caption=message, parse_mode=ParseMode.MARKDOWN)
        else:
            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Failed to send: {e}")
        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=message.replace("*","").replace("_",""))
        except Exception as e2:
            logger.error(f"Fallback failed: {e2}")

async def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID!")
    logger.info("Starting GTA Gun Van Bot...")
    await send_daily_update()
    scheduler = AsyncIOScheduler(timezone="Australia/Sydney")
    scheduler.add_job(send_daily_update, trigger="cron", hour=7, minute=0, id="daily_gunvan")
    scheduler.start()
    logger.info("Bot running — posts daily at 07:00 AM AEST.")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
