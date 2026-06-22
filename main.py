import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# Импортируем настройки PostgreSQL из database.py
from database import engine, get_db

# Импортируем функции работы с БД из services/chat.py
from services.chat import save_message, get_history

# Импортируем все функции интеграции с Oylan API
from services.oylan import (
    send_message, 
    fetch_assistants, 
    create_new_assistant, 
    clear_assistant_context
)

app = FastAPI(title="SentrySite AI - Oylan Comprehensive Enterprise Edition")


# Безопасная инициализация изолированной схемы и таблицы при старте приложения
@app.on_event('startup')
async def startup():
    async with engine.begin() as conn:
        print("⏳ Создание изолированной схемы user_schema...")
        # Создаем схему, где у твоего пользователя гарантированно есть все права
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS user_schema;"))
        
        print("⏳ Проверка и создание таблицы messages внутри user_schema...")
        raw_sql = """
        CREATE TABLE IF NOT EXISTS user_schema.messages (
            id SERIAL NOT NULL, 
            session_id VARCHAR(64), 
            role VARCHAR(16), 
            content TEXT, 
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
            PRIMARY KEY (id)
        );
        """
        await conn.execute(text(raw_sql))
    print("🚀 База данных успешно инициализирована в user_schema и готова к работе!")


# --- ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ И НАСТРОЙКИ (Имитация БД для архива отчетов) ---
REPORTS_STORAGE = {}
CURRENT_PROMPT_TEMPLATE = "Дай краткую, но professional строительно-экологическую рекомендацию."


# --- МОДЕЛИ ДАННЫХ (Pydantic Models) ---

class SiteRequest(BaseModel):
    lat: float
    lon: float
    object_type: str
    message: Optional[str] = "Проанализируй локацию"
    session_id: str = 'default'

class CoordinatesRequest(BaseModel):
    lat: float
    lon: float

class CompareRequest(BaseModel):
    object_type: str
    location_A: CoordinatesRequest
    location_B: CoordinatesRequest

class AssistantCreateRequest(BaseModel):
    name: str
    model: Optional[str] = "Oylan"

class PromptTemplateRequest(BaseModel):
    mode: str


# --- ИМИТАЦИЯ ДАННЫХ ЭКО-МОНИТОРИНГА ---
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
    return {"message": "SentrySite AI Backend with full Oylan lifecycle, database history, and reporting is running!"}

@app.get("/health")
def health():
    return {"status": "ok"}


# --- ЭНДПОИНТЫ УПРАВЛЕНИЯ АССИСТЕНТАМИ OYLAN ---

@app.get("/assistant")
async def get_assistants():
    try:
        data = await fetch_assistants()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить список: {str(e)}")


@app.post("/assistant")
async def add_assistant(req: AssistantCreateRequest):
    try:
        data = await create_new_assistant(name=req.name, model=req.model)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания ассистента: {str(e)}")


@app.delete("/assistant/{assistant_id}/contexts")
async def clear_context(assistant_id: str):
    try:
        result = await clear_assistant_context(assistant_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка очистки контекста: {str(e)}")


# --- ОСНОВНОЙ ЭНДПОИНТ ЧАТА С ПОДДЕРЖКОЙ ИСТОРИИ ИЗ БД ---

@app.post("/chat")
async def chat_with_oylan(request: SiteRequest, db: AsyncSession = Depends(get_db)):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
        
    pm25, city = get_pm25(request.lat, request.lon)
    safe = pm25 <= 5
    
    full_prompt = (
        f"Пользователь пишет: {request.message}. "
        f"Контекст эко-мониторинга для объекта '{request.object_type}': "
        f"Локация: {city} (координаты: {request.lat}, {request.lon}). "
        f"Уровень PM2.5: {pm25} мкг/м³. Это {'соответствует' if safe else 'ПРЕВЫШАЕТ'} норму. "
        f"{CURRENT_PROMPT_TEMPLATE}"
    )
    
    try:
        # 1. Тянем историю переписки из Postgres
        history = await get_history(db, request.session_id)
        
        # 2. Отправляем в Oylan
        oylan_reply = await send_message(full_prompt, history)
        
        # 3. Фиксируем диалог в базе данных
        await save_message(db, request.session_id, 'user', request.message)
        await save_message(db, request.session_id, 'assistant', oylan_reply)
        
    except Exception as e:
        print(f"Ошибка вызова Oylan API или БД: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    report_id = str(len(REPORTS_STORAGE) + 1)
    REPORTS_STORAGE[report_id] = {
        "city": city,
        "pm25": pm25,
        "object_type": request.object_type,
        "reply": oylan_reply
    }

    return {
        "report_id": report_id,
        "status": "ok",
        "city": city,
        "pm25": pm25,
        "safe": safe,
        "object_type": request.object_type,
        "reply": oylan_reply,
        "session_id": request.session_id
    }


# --- ЭНДПОИНТ ДЛЯ ПРОСМОТРА ИСТОРИИ ИЗ ПОСТГРЕСА ---

@app.get("/history/{session_id}")
async def history(session_id: str, db: AsyncSession = Depends(get_db)):
    try:
        msgs = await get_history(db, session_id, limit=50)
        return {'session_id': session_id, 'messages': msgs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- ЭНДПОИНТЫ ЭКО-АНАЛИТИКИ И ЭКСПОРТА ---

@app.get("/reports/{report_id}/export")
def export_report_to_file(report_id: str):
    if report_id not in REPORTS_STORAGE:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    
    data = REPORTS_STORAGE[report_id]
    document_text = (
        f"==================================================\n"
        f"          ЭКОЛОГИЧЕСКОЕ ЗАКЛЮЧЕНИЕ SENTRYSITE AI  \n"
        f"==================================================\n"
        f"Номер отчёта: №{report_id}\n"
        f"Город мониторинга: {data['city']}\n"
        f"Тип строительного объекта: {data['object_type']}\n"
        f"Зафиксированный уровень PM2.5: {data['pm25']} мкг/м³\n"
        f"--------------------------------------------------\n"
        f"ЭКСПЕРТНЫЙ АНАЛИЗ И РЕКОМЕНДАЦИИ ИИ АССИСТЕНТА OYLAN:\n\n"
        f"{data['reply']}\n"
    )
    
    headers = {"Content-Disposition": f"attachment; filename=SentrySite_Report_{report_id}.txt"}
    return PlainTextResponse(content=document_text, headers=headers)


@app.post("/assistant/prompt-template")
def change_ai_template(req: PromptTemplateRequest):
    global CURRENT_PROMPT_TEMPLATE
    if req.mode == "strict":
        CURRENT_PROMPT_TEMPLATE = "Дай жесткую критическую оценку с точки зрения экологических штрафов и законов РК."
    elif req.mode == "eco":
        CURRENT_PROMPT_TEMPLATE = "Предложи исключительно инновационные 'зеленые' строительные технологии."
    elif req.mode == "default":
        CURRENT_PROMPT_TEMPLATE = "Дай краткую, но профессиональную строительно-экологическую рекомендацию."
    else:
        raise HTTPException(status_code=400, detail="Неизвестный режим")
    return {"status": "success", "active_template": CURRENT_PROMPT_TEMPLATE}


@app.post("/analyze")
def analyze_by_coordinates(request: CoordinatesRequest):
    pm25, city = get_pm25(request.lat, request.lon)
    recommendation = "Зона безопасна." if pm25 <= 12.0 else "Рекомендуется спроектировать систему вентиляции."
    return {"status": "success", "detected_city": city, "pm25": pm25, "recommendation": recommendation}


@app.get("/cities")
def get_supported_cities():
    return {"supported_cities": CITY_DATA}


@app.post("/compare")
def compare_sites(req: CompareRequest):
    pm25_A, city_A = get_pm25(req.location_A.lat, req.location_A.lon)
    pm25_B, city_B = get_pm25(req.location_B.lat, req.location_B.lon)
    winner = "Location A" if pm25_A < pm25_B else "Location B"
    return {
        "object_type": req.object_type,
        "result": {"winner": winner, "recommendation": "Выбрана оптимальная площадка"},
        "details": {"location_A": {"city": city_A, "pm25": pm25_A}, "location_B": {"city": city_B, "pm25": pm25_B}}
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)