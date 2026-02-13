import json
import os

from dotenv import load_dotenv

load_dotenv()

PROXY_POOL = []
proxy_str = os.getenv("PROXY_POOL", "")
if proxy_str:
    try:
        PROXY_POOL = json.loads(proxy_str)
    except json.JSONDecodeError:
        print("Ошибка парсинга PROXY_POOL — должен быть JSON массив строк")
        PROXY_POOL = []

RUCAPTCHA_API_KEY = os.getenv("RUCAPTCHA_API_KEY")
if not RUCAPTCHA_API_KEY:
    raise ValueError("RUCAPTCHA_API_KEY не найден в .env файле")

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise ValueError("DB_URL не найден в .env файле")

PAGE_URL_POOL = [
    "https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q=840122905254",
    "https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q=30144941",
    "https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q=30148093",
]

HEADLESS = os.getenv("HEADLESS", "False").lower() == "true"
CONCURRENT_BROWSERS = 5
INTERVAL_BETWEEN_STARTS = 5  # секунд - задержка между запуском новых задач
