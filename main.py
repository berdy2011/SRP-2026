import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# Импортируем все функции интеграции с Oylan API
from services.oylan import (
    send_message, 
    fetch_assistants, 
    create_new_assistant, 
    clear_assistant_context
)

load_dotenv()

app = FastAPI(title="SentrySite AI - Oylan Comprehensive Edition")

# --- МОДЕЛИ ДАННЫХ (Pydantic Models) ---

class SiteRequest(BaseModel):
    lat: float
    lon: float
    object_type: str

class CoordinatesRequest(BaseModel):
    lat: float
    lon: float

class CompareRequest(BaseModel):
    object_type: str
    location_A: CoordinatesRequest
    location_B: CoordinatesRequest

# Модель для создания нового ассистента через API
class AssistantCreateRequest(BaseModel):
    name: str
    model: Optional[str] = "Oylan"


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
    return {"message": "SentrySite AI Backend with full Oylan lifecycle is running!"}

@app.get("/health")
def health():
    return {"status": "ok"}


# --- ЭНДПОИНТЫ ИЗ СКРИНШОТА СИСТЕМЫ OYLAN ---

# 1. GET /assistant/ — Список ассистентов
@app.get("/assistant", summary="Список ассистентов -> берем id")
async def get_assistants():
    try:
        data = await fetch_assistants()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить список: {str(e)}")

# 2. POST /assistant/ — Создать нового ассистента
@app.post("/assistant", summary="Создать нового ассистента (model: 'Oylan')")
async def add_assistant(req: AssistantCreateRequest):
    try:
        data = await create_new_assistant(name=req.name, model=req.model)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания ассистента: {str(e)}")

# 3. POST /assistant/{id}/interactions/ — Отправить сообщение -> получить ответ
# Привязан к нашей логике SiteRequest для бесшовного анализа координат!
@app.post("/chat", summary="Отправить сообщение ассистенту (Экспресс-анализ)")
async def chat_with_oylan(request: SiteRequest):
    pm25, city = get_pm25(request.lat, request.lon)
    safe = pm25 <= 5
    
    prompt = (
        f"Проанализируй экологическую обстановку для строительного объекта '{request.object_type}'. "
        f"Локация: {city} (координаты: {request.lat}, {request.lon}). "
        f"Текущий зафиксированный уровень мелкодисперсных частиц PM2.5 составляет {pm25} мкг/м³. "
        f"Это {'соответствует' if safe else 'ПРЕВЫШАЕТ'} норму ВОЗ. "
        f"Дай краткую, но профессиональную строительно-экологическую рекомендацию."
    )
    
    try:
        oylan_reply = await send_message(prompt)
    except Exception as e:
        print(f"Ошибка вызова Oylan API: {e}")
        oylan_reply = f"Интеграция временно недоступна. Техническая сводка: PM2.5 = {pm25} мкг/м³ в городе {city}."

    return {
        "status": "ok",
        "city": city,
        "pm25": pm25,
        "safe": safe,
        "object_type": request.object_type,
        "reply": oylan_reply
    }

# 4. DELETE /assistant/{id}/contexts/ — Очистить контекст файла/истории
@app.delete("/assistant/{assistant_id}/contexts", summary="Очистить контекст и историю чата ассистента")
async def clear_context(assistant_id: str):
    try:
        result = await clear_assistant_context(assistant_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка очистки контекста: {str(e)}")


# --- ОСТАЛЬНЫЕ ИНЖЕНЕРНЫЕ ЭНДПОИНТЫ ---

@app.post("/analyze", summary="Получить рекомендацию только по координатам")
def analyze_by_coordinates(request: CoordinatesRequest):
    pm25, city = get_pm25(request.lat, request.lon)
    
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

@app.get("/cities", summary="Список поддерживаемых городов")
def get_supported_cities():
    return {
        "description": "Список городов, доступных для экспресс-анализа грунта и воздуха",
        "supported_cities": CITY_DATA
    }

@app.post("/compare", summary="Сравнение двух строительных площадок")
def compare_sites(req: CompareRequest):
    pm25_A, city_A = get_pm25(req.location_A.lat, req.location_A.lon)
    pm25_B, city_B = get_pm25(req.location_B.lat, req.location_B.lon)
    
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)