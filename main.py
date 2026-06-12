from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI(title="SentrySite AI - Custom Edition")

# Базовая модель для координат одной точки
class SiteRequest(BaseModel):
    lat: float
    lon: float
    object_type: str

# Новая модель для сравнения двух локаций
class CompareRequest(BaseModel):
    object_type: str
    location_A: List[float]  # [широта, долгота] для Точки А
    location_B: List[float]  # [широта, долгота] для Точки Б


# Локальная база данных PM2.5 по городам Казахстана
CITY_DATA = {
    "astana": {"pm25": 23.5, "city": "Астана"},
    "almaty": {"pm25": 35.2, "city": "Алматы"},
    "bishkek": {"pm25": 28.1, "city": "Бишкек"},
}

def get_pm25(lat: float, lon: float):
    # Астана
    if 51.0 <= lat <= 51.5 and 71.0 <= lon <= 72.0:
        return 23.5, "Астана"
    # Алматы
    if 43.0 <= lat <= 43.5 and 76.5 <= lon <= 77.5:
        return 35.2, "Алматы"
    # Дефолт
    return 20.0, "Неизвестный город"


# --- БАЗОВЫЕ ЭНДПОИНТЫ (Из методички) ---

@app.get("/")
def root():
    return {"message": "SentrySite AI Backend is running!"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat")
def chat(request: SiteRequest):
    pm25, city = get_pm25(request.lat, request.lon)
    safe = pm25 <= 5
    return {
        "status": "ok",
        "city": city,
        "pm25": pm25,
        "safe": safe,
        "reply": "Безопасно ✅" if safe else f"Опасно! PM2.5 = {pm25} мкг/м³ — выше нормы ВОЗ в {round(pm25/5, 1)}x ❌"
    }


# --- ТВОИ СОБСТВЕННЫЕ УНИКАЛЬНЫЕ ЭНДПОИНТЫ (Для ментора) ---

# 1. Твой кастомный GET-эндпоинт: Список поддерживаемых городов
@app.get("/cities")
def get_supported_cities():
    """Возвращает список доступных городов и их экологический статус"""
    return {
        "description": "Список городов, доступных для экспресс-анализа грунта и воздуха",
        "supported_cities": CITY_DATA
    }

# 2. Твой кастомный POST-эндпоинт: Сравнение двух строительных площадок
@app.post("/compare")
def compare_sites(req: CompareRequest):
    """Сравнивает две локации и выбирает лучшую для строительства"""
    # Анализируем первую точку
    pm25_A, city_A = get_pm25(req.location_A[0], req.location_A[1])
    # Анализируем вторую точку
    pm25_B, city_B = get_pm25(req.location_B[0], req.location_B[1])
    
    # Логика выбора лучшей площадки (где PM2.5 меньше)
    if pm25_A < pm25_B:
        best_location = "Location A"
        difference = round(pm25_B - pm25_A, 1)
        recommendation = f"Точка А предпочтительнее для объекта '{req.object_type}', так как уровень загрязнения там ниже на {difference} мкг/м³."
    elif pm25_B < pm25_A:
        best_location = "Location B"
        difference = round(pm25_A - pm25_B, 1)
        recommendation = f"Точка Б предпочтительнее для объекта '{req.object_type}', так как уровень загрязнения там ниже на {difference} мкг/м³."
    else:
        best_location = "Both"
        recommendation = "Обе локации имеют одинаковый уровень экологического риска."

    return {
        "object_type": req.object_type,
        "result": {
            "winner": best_location,
            "recommendation": recommendation
        },
        "details": {
            "location_A": {"city": city_A, "pm25": pm25_A},
            "location_B": {"city": city_B, "pm25": pm25_B}
        }
    }