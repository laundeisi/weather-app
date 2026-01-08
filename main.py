# main.py - 完整可用的天气应用
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import csv
import aiohttp
import os

# ========== 模型定义 ==========
Base = declarative_base()

class City(Base):
    __tablename__ = "cities"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    temperature = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

class DefaultCity(Base):
    __tablename__ = "default_cities"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
# ========== 模型定义结束 ==========

# 数据库设置
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cities.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建表
Base.metadata.create_all(bind=engine)

# ========== 关键！必须创建 app 实例 ==========
app = FastAPI()
# ========== 关键结束 ==========

templates = Jinja2Templates(directory="templates")

# 工具函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def fetch_weather(latitude: float, longitude: float):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("current_weather", {}).get("temperature")
    except Exception as e:
        print(f"获取天气失败: {e}")
        return None

# 路由
@app.get("/")
async def read_root(request: Request, db: SessionLocal = Depends(get_db)):
    cities = db.query(City).all()
    return templates.TemplateResponse("index.html", {"request": request, "cities": cities})

@app.post("/cities/add")
async def add_city(name: str = Form(...), latitude: float = Form(...), longitude: float = Form(...), db: SessionLocal = Depends(get_db)):
    city = City(name=name, latitude=latitude, longitude=longitude)
    db.add(city)
    db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/cities/remove/{city_id}")
async def remove_city(city_id: int, db: SessionLocal = Depends(get_db)):
    city = db.query(City).filter(City.id == city_id).first()
    if city:
        db.delete(city)
        db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/cities/reset")
async def reset_cities(db: SessionLocal = Depends(get_db)):
    db.query(City).delete()
    default_cities = [
        ("London", 51.5074, -0.1278),
        ("Paris", 48.8566, 2.3522),
        ("Berlin", 52.5200, 13.4050),
        ("Rome", 41.9028, 12.4964),
        ("Madrid", 40.4168, -3.7038)
    ]
    for name, lat, lon in default_cities:
        db.add(City(name=name, latitude=lat, longitude=lon))
    db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/cities/update")
async def update_weather(db: SessionLocal = Depends(get_db)):
    cities = db.query(City).all()
    for city in cities:
        temp = await fetch_weather(city.latitude, city.longitude)
        if temp is not None:
            city.temperature = temp
            city.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse("/", status_code=303)

@app.on_event("startup")
def populate_default_cities():
    db = SessionLocal()
    try:
        if not db.query(DefaultCity).first():
            print("初始化默认城市数据...")
            try:
                with open("europe.csv", "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        db.add(DefaultCity(
                            name=row["name"],
                            latitude=float(row["latitude"]),
                            longitude=float(row["longitude"])
                        ))
                db.commit()
                print("默认城市数据初始化完成")
            except FileNotFoundError:
                print("europe.csv 文件未找到，跳过默认城市初始化")
    finally:
        db.close()

# 注意：文件结尾不要有 if __name__ == "__main__" 除非你知道在做什么