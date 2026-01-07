from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, City, DefaultCity
from datetime import datetime
import csv
import aiohttp

# Database setup
DATABASE_URL = "sqlite:///./cities.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI setup
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Utility functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def fetch_weather(latitude: float, longitude: float):
    async with aiohttp.ClientSession() as session:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
        async with session.get(url) as response:
            data = await response.json()
            return data["current_weather"]["temperature"]

# Routes
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
    default_cities = db.query(DefaultCity).all()
    for default in default_cities:
        db.add(City(name=default.name, latitude=default.latitude, longitude=default.longitude))
    db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/cities/update")
async def update_weather(db: SessionLocal = Depends(get_db)):
    cities = db.query(City).all()
    for city in cities:
        city.temperature = await fetch_weather(city.latitude, city.longitude)
        city.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse("/", status_code=303)

@app.on_event("startup")
def populate_default_cities():
    db = SessionLocal()
    if not db.query(DefaultCity).first():
        with open("europe.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                db.add(DefaultCity(name=row["name"], latitude=float(row["latitude"]), longitude=float(row["longitude"])))
        db.commit()
    db.close()