import logging
import os
import platform
import random
import subprocess
from pathlib import Path

from database import get_db
from fastapi import Depends, FastAPI, HTTPException, Query
from models import Cookie
from sqlalchemy.orm import Session

app = FastAPI()

# Путь к директории cookie_collector (относительно api/main.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLLECTOR_DIR = PROJECT_ROOT / "cookie_collector"
PID_FILE = PROJECT_ROOT / ".collector.pid"

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler()],
)


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


# ====== Запуск/Остановка сборки куков ======

def is_running():
    if not PID_FILE.exists():
        return False
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        # Проверка существования процесса (кросс-платформенная)
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return False


@app.post("/start_cookie_collector")
async def start_collector():
    if is_running():
        raise HTTPException(409, detail="Сборщик куков уже запущен")

    cmd = ["uv", "run", "python", "main.py"]

    # Параметры для создания полностью независимого процесса
    kwargs = {
        "cwd": str(COLLECTOR_DIR),
        "env": os.environ.copy(),  # передаём .env / переменные
        "stdout": subprocess.DEVNULL,  # или open("collector.out", "a")
        "stderr": subprocess.DEVNULL,  # или тот же файл
        "start_new_session": True,  # отрывает от сессии
    }

    # Windows-специфично: CREATE_NEW_PROCESS_GROUP + DETACHED
    if platform.system() == "Windows":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS  # 0x00000008
            | subprocess.CREATE_NO_WINDOW  # без консольного окна
        )
    else:
        # Linux/macOS: setsid для полной отцепки
        kwargs["preexec_fn"] = os.setsid
    try:
        proc = subprocess.Popen(cmd, **kwargs)

        # Сохраняем PID — полезно для остановки / проверки
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))

        return {
            "status": "launched",
            "pid": proc.pid,
            "note": "Процесс полностью независимый, не привязан к API",
        }

    except Exception as e:
        raise HTTPException(500, detail=f"Не удалось запустить сборщик: {str(e)}")


@app.post("/stop_cookie_collector")
async def stop_collector():
    if not is_running():
        return {"status": "not running"}

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        if platform.system() == "Windows":
            # На Windows проще убить по PID через taskkill
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
        else:
            # Linux: убиваем группу процессов (pgid = pid при setsid)
            os.killpg(os.getpgid(pid), 15)   # SIGTERM группе
            # Если не умер — жёстко
            import time
            time.sleep(4)
            try:
                os.killpg(os.getpgid(pid), 9)  # SIGKILL
            except ProcessLookupError:
                pass

        PID_FILE.unlink(missing_ok=True)
        return {"status": "stopped"}

    except Exception as e:
        raise HTTPException(500, detail=f"Ошибка при остановке: {str(e)}")


@app.get("/collector_status")
async def collector_status():
    return {
        "running": is_running(),
        "pid_file_exists": PID_FILE.exists()
    }
