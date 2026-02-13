import json
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Cookie(Base):
    __tablename__ = "cookies"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    cookies_json = Column(String)
    proxy = Column(String)
    after_captcha = Column(Boolean, default=False, nullable=False)

    def to_dict(self):
        return json.loads(self.cookies_json)
