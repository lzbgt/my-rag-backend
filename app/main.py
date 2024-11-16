from app.config import *
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from sqlalchemy.dialects.mysql import LONGTEXT
from pydantic import BaseModel
import requests
from sqlalchemy import Column, Integer, String, UniqueConstraint, create_engine, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.utils.mylogger import get_logger
import uvicorn
from datetime import datetime, timedelta
from fastapi.middleware.gzip import GZipMiddleware
import json
import orjson
from sqlalchemy.orm import class_mapper
from typing import Optional
from app.utils.random import generate_random_four_chars


def sqlalchemy_to_dict(obj):
    """将 SQLAlchemy 对象转换为字典"""
    columns = [c.key for c in class_mapper(obj.__class__).columns]
    return {c: getattr(obj, c) for c in columns}


def sqlalchemy_to_json(obj):
    """将 SQLAlchemy 对象转换为 JSON 字符串"""
    obj_dict = sqlalchemy_to_dict(obj)
    return orjson.dumps(obj_dict).decode('utf-8')


logger = get_logger(__name__)

# Database Setup
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class BaseRecord(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    create_time = Column(DateTime, default=datetime.now())
    update_time = Column(DateTime, default=datetime.now(),
                         onupdate=datetime.now())


class User(BaseRecord):
    __tablename__ = 'users'
    openid = Column(String(255), unique=True, index=True)
    unionid = Column(String(255))
    session_key = Column(String(255))
    nick_name = Column(String(255))
    avatar_url = Column(String(512))
    mobile = Column(String(13), unique=True, index=True)
    realname = Column(String(255))
    activate_code = Column(String(255))


class ActionLog(BaseRecord):
    __tablename__ = 'action_logs'
    user_id = Column(Integer)
    action = Column(String(255), nullable=True)
    detail = Column(JSON, nullable=True)


class ActivationCode(BaseRecord):
    __tablename__ = 'activation_codes'
    code = Column(String(255))
    user_id = Column(Integer)


class PaperAnswer(BaseRecord):
    __tablename__ = 'paper_answers'
    school = Column(Integer, index=True)
    paper_id = Column(Integer, index=True)
    q = Column(LONGTEXT)
    a = Column(LONGTEXT)

    __table_args__ = (
        UniqueConstraint('school', 'paper_id', name='uix_school_paper'),
    )


# Create DB tables
Base.metadata.create_all(bind=engine)

# Pydantic model for login request


class WxProfile(BaseModel):
    openid: str
    nickname: Optional[str] = ""
    avatar_url: Optional[str] = ""
    realname: Optional[str] = ""
    activate_code: Optional[str] = ""


class QAResponse(BaseModel):
    school: int
    paper_id: int
    q: str
    a: str


# FastAPI app
app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Dependency to get DB session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility to fetch openid and session_key from WeChat


def get_wechat_openid_session_key(code: str):
    params = {
        "appid": WECHAT_APPID,
        "secret": WECHAT_SECRET,
        "js_code": code,
        "grant_type": "authorization_code"
    }
    response = requests.get(WECHAT_LOGIN_URL, params=params)
    if response.status_code != 200:
        raise HTTPException(
            status_code=400, detail="WeChat API request failed")
    data = response.json()
    if "openid" not in data or "session_key" not in data:
        raise HTTPException(status_code=400, detail="Invalid WeChat response")

    logger.info(f"session data: {data}")

    return data["openid"], data["unionid"], data["session_key"]

# Route to handle wx.login callback


def verify_secret(sec: str):
    if sec != MY_API_SEC:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret key",
        )


@app.get("/wx-login")
def wx_login(code: str, db: Session = Depends(get_db), sec: str = Depends(verify_secret)):
    try:
        openid, unionid, session_key = get_wechat_openid_session_key(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        f"openid: {openid}, session_key: {session_key}, unionid: {unionid}")

    # Check if the user exists
    user = db.query(User).filter(User.openid == openid).first()

    if user:
        # Update session_key if user exists
        user.session_key = session_key
        user.unionid = unionid
    else:
        # Create a new user if not exists
        user = User(openid=openid, session_key=session_key, unionid=unionid)
        db.add(user)

    db.commit()

    return {"openid": openid, "session_key": session_key}


@app.get("/wx-profile", response_model=WxProfile)
def get_wx_profile(openid: str, db: Session = Depends(get_db), sec: str = Depends(verify_secret)):
    try:
        user = db.query(User).filter(User.openid == openid).first()
        if user:
            return user
        else:
            raise HTTPException(status_code=404, detail="用户不存在")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/wx-profile")
def new_wx_profile(profile: WxProfile, db: Session = Depends(get_db), sec: str = Depends(verify_secret)):
    try:
        user = db.query(User).filter(User.openid == profile.openid).first()
        if user:
            if profile.nickname:
                user.nick_name = profile.nickname
            if profile.avatar_url:
                user.avatar_url = profile.avatar_url
            if profile.activate_code:
                user.activate_code = profile.activate_code
                ac = db.query(ActivationCode).filter(ActivationCode.code ==
                                                     profile.activate_code).first()
                if not ac:
                    raise HTTPException(status_code=400, detail="激活码不存在")
                if ac.user_id and ac.user_id != user.id:
                    raise HTTPException(status_code=400, detail="激活码已被其他人使用过了")

                if ac.user_id != user.id:
                    ac.user_id = user.id
            db.commit()
            return {"message": "Profile updated successfully"}
        else:
            return {"message": "User not found"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/paper_answers", response_model=QAResponse)
def get_paper_answers(school: int, paper_id: int, db: Session = Depends(get_db), openid: str = "", sec: str = Depends(verify_secret)):
    logger.info(f"user: {openid}, school: {school}, paper_id: {paper_id}")
    if openid:
        user = db.query(User).filter(User.openid == openid).first()
        if not user:
            raise HTTPException(status_code=400, detail="用户不存在")
        r = db.query(ActivationCode).filter(ActivationCode.user_id ==
                                            user.id).first()
        if not r:
            raise HTTPException(status_code=400, detail="用户未激活")
        ActionLog(user_id=user.id, action="get_paper_answers",
                  detail={"school": school, "paper_id": paper_id})

    r = db.query(PaperAnswer).filter(PaperAnswer.paper_id ==
                                     paper_id, PaperAnswer.school == school).first()
    if not r:
        qa = requests.post("http://xx.brucelu.top:8000/api/qa", params={
            "school": school,
            "paper_id": paper_id,
            "sec": LLM_API_SEC
        }, timeout=60*10)
        if qa.status_code != 200:
            logger.error(qa.text)
            raise HTTPException(500, detail=qa.text)
        qa_data = qa.json()
        item = PaperAnswer(paper_id=paper_id, school=school,
                           q=qa_data["paper"], a=qa_data["answer"])
        db.add(item)
        db.commit()
        db.refresh(item)
        r = item

    return r


@app.get("/activate_code")
def gen_activation_code(sec: str, db: Session = Depends(get_db)):
    if sec != MY_ACTIVATE_CODE_SEC:
        raise HTTPException(status_code=400, detail="Invalid secret")

    r = generate_random_four_chars()
    while db.query(ActivationCode).filter(
            ActivationCode.code == r).first() is not None:
        r = generate_random_four_chars()

    db.add(ActivationCode(code=r))
    db.commit()

    return {
        "data": r
    }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, workers=4)
