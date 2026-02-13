import logging
import random

from database import get_db
from fastapi import Depends, FastAPI, Query
from models import Cookie
from sqlalchemy.orm import Session

app = FastAPI()

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
