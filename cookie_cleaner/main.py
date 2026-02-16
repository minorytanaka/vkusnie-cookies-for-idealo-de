import logging
from datetime import datetime
import time
from sqlalchemy import create_engine, func, Boolean, Column, DateTime, Integer, String, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, declarative_base
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ------------------- Настройки -------------------
DB_USER = "postgres"
DB_PASS = "secretpassword"
DB_NAME = "cookies"
DB_HOST = "localhost"
DB_PORT = 5432

MIN_COUNT_TO_CLEAN = 15
INTERVAL_MINUTES = 25

# ------------------- Логирование -------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("cookie-cleaner")


Base = declarative_base()


class Cookie(Base):
    __tablename__ = "cookies"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    cookies_json = Column(String)
    proxy = Column(String)
    after_captcha = Column(Boolean, default=False, nullable=False)


# ------------------- Подключение к БД -------------------
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def cleanup_old_cookies():
    try:
        with SessionLocal() as session:
            total_count = session.query(func.count(Cookie.id)).scalar()
            
            if total_count < MIN_COUNT_TO_CLEAN:
                logger.info(f"Записей всего {total_count} < {MIN_COUNT_TO_CLEAN} → пропускаем")
                return

            to_delete = total_count // 2
            logger.info(f"Найдено {total_count} записей → удаляем {to_delete} самых старых")

            # Подзапрос на самые старые id
            subq = (
                session.query(Cookie.id)
                .order_by(Cookie.timestamp.asc())
                .limit(to_delete)
                .subquery()
            )

            # Удаляем по id из подзапроса
            stmt = (
                delete(Cookie)
                .where(Cookie.id.in_(subq))
            )

            result = session.execute(stmt)
            session.commit()

            logger.info(f"Удалено {result.rowcount} записей")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка базы: {e}", exc_info=True)
    except Exception as e:
        logger.exception(f"Неожиданная ошибка: {e}")


def main():
    scheduler = BackgroundScheduler()
    
    # Запускаем каждые INTERVAL_MINUTES минут
    scheduler.add_job(
        cleanup_old_cookies,
        trigger=IntervalTrigger(minutes=INTERVAL_MINUTES),
        id='cookie_cleanup_job',
        name='Удаление старых cookies каждые 40 минут',
        replace_existing=True
    )

    logger.info(f"Планировщик запущен. Очистка каждые {INTERVAL_MINUTES} минут. "
                f"Минимальное количество записей для очистки: {MIN_COUNT_TO_CLEAN}")

    try:
        scheduler.start()
        # Держим процесс живым
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановка планировщика...")
        scheduler.shutdown()
        logger.info("Программа завершена")


if __name__ == "__main__":
    main()
