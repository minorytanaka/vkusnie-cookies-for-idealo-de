import asyncio
import datetime
import json
import logging
import random
import sys
import os


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.models import Base, Cookie
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import config
from collector import get_cookies_via_playwright
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("collector")


async def collector_task(task_id: int, session_factory: sessionmaker):
    """Один бесконечный сборщик куки (работает в своём цикле)"""

    logger.info(f"[collector-{task_id}] Запущен")

    while True:
        try:
            page_url = random.choice(config.PAGE_URL_POOL)
            logger.info(f"[collector-{task_id}] Начинаем сбор → {page_url}")

            result: Optional[tuple[dict, str, bool]] = await get_cookies_via_playwright(
                page_url=page_url,
                proxy_pool=config.PROXY_POOL,
                rucaptcha_api_key=config.RUCAPTCHA_API_KEY,
                headless=config.HEADLESS,
            )

            if result:
                cookies, used_proxy, after_captcha = result
                db_session = session_factory()
                try:
                    new_cookie = Cookie(
                        cookies_json=json.dumps(cookies),
                        proxy=used_proxy,
                        after_captcha=after_captcha,
                    )
                    db_session.add(new_cookie)
                    db_session.commit()
                    logger.info(
                        f"[collector-{task_id}] Куки сохранены | "
                        f"proxy={used_proxy} | after_captcha={after_captcha} | {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"
                    )
                finally:
                    db_session.close()
            else:
                logger.warning(f"[collector-{task_id}] Не удалось получить куки")

        except Exception as e:
            logger.exception(f"[collector-{task_id}] Ошибка в цикле")

        # небольшая рандомизированная пауза между попытками одного сборщика
        await asyncio.sleep(random.uniform(5, 6))


async def main():
    logger.info(
        f"Запуск коллектора | параллельных браузеров = {config.CONCURRENT_BROWSERS}"
    )
    engine = create_engine(config.DB_URL)  # PostgreSQL из .env
    Base.metadata.create_all(bind=engine)  # Создание таблицы (если нет)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    tasks = []
    for i in range(1, config.CONCURRENT_BROWSERS + 1):
        task = asyncio.create_task(collector_task(i, session_factory))
        tasks.append(task)

        # небольшая задержка между стартом задач, чтобы не перегружать систему сразу
        if i < config.CONCURRENT_BROWSERS:
            await asyncio.sleep(config.INTERVAL_BETWEEN_STARTS)

    # ждём бесконечно (или до Ctrl+C)
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        logger.info("Запуск коллектора куки...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка по Ctrl+C")
    except Exception as e:
        logger.exception("Критическая ошибка при запуске коллектора")
