from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI(title="SentrySite AI - Verified Edition")

# --- МОДЕЛИ ДАННЫХ (Pydantic Models) ---

# 1. Твоя оригинальная модель для чата (ОСТАЕТСЯ КАК БЫЛО)
class SiteRequest(BaseModel):
    lat: float
    lon: float
    object_type: str

# 2. НОВАЯ модель для второго эндпоинта (только координаты)
class CoordinatesRequest(BaseModel):
    lat: float
    lon: float

# 3. Модель для сравнения двух строительных площадок
class CompareRequest(BaseModel):
    object_type: str
    location_A: List[float]
    location_B: List[float]


# --- ИМИТАЦИЯ БАЗЫ ДАННЫХ ---
CITY_DATA = {
    "astana": {"pm25": 23.5, "city": "Астана"},
    "almaty": {"pm25": 35.2, "city": "Алматы"},
    "bishkek": {"pm25": 28.1, "city": "Бишкек"},
}

def get_pm25(lat: float, lon: float):
    if 51.0 <= lat <= 51.5 and 71.0 <= lon <= 72.0:
        return 23.5, "Астана"
    if 43.0 <= lat <= 43.5 and 76.5 <= lon <= 77.5:
        return 35.2, "Алматы"
    return 20.0, "Неизвестный город"


# --- СИСТЕМНЫЕ ЭНДПОИНТЫ ---
@app.get("/")
def root():
    return {"message": "SentrySite AI Backend is running!"}

@app.get("/health")
def health():
    return {"status": "ok"}


# --- ИНЖЕНЕРНЫЕ ЭНДПОИНТЫ ---

# 1. ТВОЙ СТАРЫЙ ЧАТ (Остался точно таким же, как и был)
@app.post("/chat", summary="Экспресс-анализ по объекту и координатам")
def old_chat(request: SiteRequest):
    pm25, city = get_pm25(request.lat, request.lon)
    safe = pm25 <= 5
    return {
        "status": "ok",
        "city": city,
        "pm25": pm25,
        "safe": safe,
        "reply": "Безопасно ✅" if safe else f"Опасно! PM2.5 = {pm25} мкг/м³ — выше нормы ВОЗ в {round(pm25/5, 1)}x ❌",
        "object_type": request.object_type  # Возвращаем тип объекта назад
    }

# 2. НОВЫЙ ЭНДПОИНТ (Принимает ТОЛЬКО координаты и дает чистую рекомендацию)
@app.post("/analyze", summary="Получить рекомендацию только по координатам")
def analyze_by_coordinates(request: CoordinatesRequest):
    """Принимает исключительно широту и долготу, возвращает эко-заключение"""
    pm25, city = get_pm25(request.lat, request.lon)
    
    # Формируем логику рекомендаций
    if pm25 <= 12.0:
        recommendation = "Зона полностью безопасна. Дополнительная фильтрация не требуется."
    else:
        recommendation = f"Внимание, это {city}. Уровень PM2.5 равен {pm25} мкг/м³. Рекомендуется спроектировать усиленную систему вентиляции."

    return {
        "status": "success",
        "detected_city": city,
        "pm25": pm25,
        "recommendation": recommendation
    }

# 3. СПИСОК ГОРОДОВ
@app.get("/cities", summary="Список поддерживаемых городов")
def get_supported_cities():
    return {
        "description": "Список городов, доступных для экспресс-анализа грунта и воздуха",
        "supported_cities": CITY_DATA
    }

# 4. СРАВНЕНИЕ ДВУХ СТРОИТЕЛЬНЫХ ПЛОЩАДОК
@app.post("/compare", summary="Сравнение двух строительных площадок")
def compare_sites(req: CompareRequest):
    pm25_A, city_A = get_pm25(req.location_A[0], req.location_A[1])
    pm25_B, city_B = get_pm25(req.location_B[0], req.location_B[1])
    
    if pm25_A < pm25_B:
        winner = "Location A"
        difference = round(pm25_B - pm25_A, 1)
        recommendation = f"Точка А предпочтительнее для объекта '{req.object_type}', так как уровень загрязнения там ниже на {difference} мкг/м³."
    elif pm25_B < pm25_A:
        winner = "Location B"
        difference = round(pm25_A - pm25_B, 1)
        recommendation = f"Точка Б предпочтительнее для объекта '{req.object_type}', так как уровень загрязнения там ниже на {difference} мкг/м³."
    else:
        winner = "Both"
        recommendation = "Обе локации имеют одинаковый уровень экологического риска."

    return {
        "object_type": req.object_type,
        "result": {
            "winner": winner,
            "recommendation": recommendation
        },
        "details": {
            "location_A": {"city": city_A, "pm25": pm25_A},
            "location_B": {"city": city_B, "pm25": pm25_B}
        }
    }