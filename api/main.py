import logging
import os
import platform
import random
import signal
import subprocess
from pathlib import Path

from database import get_db
from fastapi import Depends, FastAPI, HTTPException, Query
from models import Cookie
from sqlalchemy.orm import Session

app = FastAPI()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLLECTOR_DIR = PROJECT_ROOT / "cookie_collector"
CLEANER_DIR = PROJECT_ROOT / "cookie_cleaner"
COLLECTOR_PID_FILE = PROJECT_ROOT / ".collector.pid"
CLEANER_PID_FILE = PROJECT_ROOT / ".cleaner.pid"

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler()],
)


# ====== Утилиты управления процессами ======


def _is_process_running(pid_file: Path) -> bool:
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, OSError):
        pid_file.unlink(missing_ok=True)
        return False


def _launch_detached(cmd: list[str], cwd: Path, pid_file: Path) -> int:
    kwargs: dict = {
        "cwd": str(cwd),
        "env": os.environ.copy(),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "start_new_session": True,
    }

    if platform.system() == "Windows":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        kwargs["preexec_fn"] = os.setsid

    proc = subprocess.Popen(cmd, **kwargs)
    pid_file.write_text(str(proc.pid))
    return proc.pid


def _kill_process_tree(pid_file: Path) -> bool:
    """Останавливает процесс и всю его группу. Возвращает True, если что-то убито."""
    if not pid_file.exists():
        return False

    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        pid_file.unlink(missing_ok=True)
        return False

    killed = False

    if platform.system() == "Windows":
        result = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
        )
        killed = result.returncode == 0
    else:
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
            killed = True
            logger.info(f"Отправлен SIGTERM группе процессов pgid={pgid}")
        except ProcessLookupError:
            logger.info(f"Процесс pid={pid} уже не существует")
        except OSError as e:
            logger.error(f"Ошибка при убийстве процесса pid={pid}: {e}")

    pid_file.unlink(missing_ok=True)
    return killed


def _delete_all_cookies(db: Session) -> int:
    """Удаляет все куки из БД. Возвращает количество удалённых записей."""
    count = db.query(Cookie).delete()
    db.commit()
    logger.info(f"Удалено {count} куки из базы данных")
    return count


# ====== Получение куки ======


@app.get("/latest-cookie")
def get_latest_cookie(
    after_captcha: bool | None = Query(
        None, description="True = после капчи, False = без капчи, None = любая"
    ),
    db: Session = Depends(get_db),
):
    query = db.query(Cookie).order_by(Cookie.timestamp.desc())
    if after_captcha is not None:
        query = query.filter(Cookie.after_captcha == after_captcha)
    cookie = query.first()
    if not cookie:
        return {"error": "Нет подходящих куки"}
    return {
        "id": cookie.id,
        "cookies": cookie.to_dict(),
        "proxy": cookie.proxy,
        "after_captcha": cookie.after_captcha,
        "timestamp": cookie.timestamp.isoformat(),
    }


@app.get("/random-cookie")
def get_random_cookie(
    after_captcha: bool | None = Query(
        None, description="True = после капчи, False = без капчи, None = любая"
    ),
    db: Session = Depends(get_db),
):
    query = db.query(Cookie)
    if after_captcha is not None:
        query = query.filter(Cookie.after_captcha == after_captcha)
    cookies_list = query.all()
    if not cookies_list:
        return {"error": "Нет подходящих куки"}
    random_cookie = random.choice(cookies_list)
    return {
        "id": random_cookie.id,
        "cookies": random_cookie.to_dict(),
        "proxy": random_cookie.proxy,
        "after_captcha": random_cookie.after_captcha,
        "timestamp": random_cookie.timestamp.isoformat(),
    }


# ====== Сборщик куки ======


@app.post("/start_cookie_collector")
async def start_collector():
    if _is_process_running(COLLECTOR_PID_FILE):
        raise HTTPException(409, detail="Сборщик куков уже запущен")

    try:
        pid = _launch_detached(
            cmd=["uv", "run", "python", "run_collector.py"],
            cwd=COLLECTOR_DIR,
            pid_file=COLLECTOR_PID_FILE,
        )
        return {
            "status": "launched",
            "pid": pid,
        }
    except Exception as e:
        raise HTTPException(500, detail=f"Не удалось запустить сборщик: {e}")


@app.post("/stop_cookie_collector")
async def stop_collector(db: Session = Depends(get_db)):
    killed = _kill_process_tree(COLLECTOR_PID_FILE)
    deleted = _delete_all_cookies(db)

    return {
        "status": "stopped",
        "process_killed": killed,
        "cookies_deleted": deleted,
    }


# ====== Чистильщик куки ======


@app.post("/start_cookie_cleaner")
async def start_cleaner():
    if _is_process_running(CLEANER_PID_FILE):
        raise HTTPException(409, detail="Чистильщик куков уже запущен")

    try:
        pid = _launch_detached(
            cmd=["uv", "run", "python", "main.py"],
            cwd=CLEANER_DIR,
            pid_file=CLEANER_PID_FILE,
        )
        return {
            "status": "launched",
            "pid": pid,
        }
    except Exception as e:
        raise HTTPException(500, detail=f"Не удалось запустить чистильщик: {e}")


@app.post("/stop_cookie_cleaner")
async def stop_cleaner(db: Session = Depends(get_db)):
    killed = _kill_process_tree(CLEANER_PID_FILE)
    deleted = _delete_all_cookies(db)

    return {
        "status": "stopped",
        "process_killed": killed,
        "cookies_deleted": deleted,
    }
