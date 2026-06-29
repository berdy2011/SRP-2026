import os
import httpx
import asyncio
from google import genai
from google.genai import types
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# Загрузка переменных окружения для внешнего API Oylan
API_KEY = os.getenv('OYLAN_API_KEY')
ASSISTANT_ID = os.getenv('OYLAN_ASSISTANT_ID')
BASE_URL = os.getenv('OYLAN_BASE_URL')

HEADERS = {
    'Authorization': f'Api-Key {API_KEY}',
    'Content-Type': 'application/json',
    'accept': 'application/json'
}

# Инициализация клиента Google GenAI
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
client_ai = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

if not client_ai:
    print("⚠️ Внимание: GEMINI_API_KEY не найден в файле .env")


async def generate_local_response(user_msg: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """Асинхронно генерирует чистый ответ без эффекта 'снежного кома' и повторений из истории"""
    if not client_ai:
        return "[SentrySite AI]: Автономный режим. Добавьте GEMINI_API_KEY в .env"
    
    config = types.GenerateContentConfig(
        system_instruction=(
            "Ты — Oylan AI Assistant, модуль экологического мониторинга SentrySite AI. "
            "Твой создатель — Бердыхан. Ты всегда общаешься напрямую с ним. "
            "ЖЕСТКОЕ ПРАВИЛО: Отвечай только на текущий вопрос пользователя. "
            "Если тебя спрашивают про время суток, анекдоты, приветствия или вежливость — "
            "отвечай живо, емко и человечно. Тебе КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО добавлять абзацы "
            "про вентиляцию, многоступенчатую фильтрацию, ЖК и строительные рекомендации, "
            "если тебя об этом не спросили прямо в последней реплике."
        ),
        temperature=0.2
    )

    contents = []
    # Проверяем, носит ли текущий запрос технический характер
    is_technical_query = any(word in user_msg.lower() for word in ["датчик", "вентиляц", "фильтр", "pm2.5", "инфильтрац"])
    
    if history:
        for msg in history:
            role = msg.get('role', 'user')
            content_text = msg.get('content', '')
            
            if role == 'assistant' or role == 'model':
                # 1. Защита от строительных шаблонов: убираем старый бред, если текущий вопрос — просто болтовня
                if not is_technical_query and any(bad in content_text.lower() for bad in ["вентиляц", "объект", "комплекс", "рекомендац"]):
                    continue
                
                # 2. Защита от эффекта 'попугая': срезаем старые приветствия и шутки из памяти модели,
                # чтобы она не дублировала их бесконечно в новых ответах
                if not is_technical_query:
                    content_text = content_text.replace("Привет, Бердыхан!", "").replace("На связи.", "").strip()
                    if any(joke_word in content_text for joke_word in ["Хэллоуин", "OCT 31", "Рождество", "шутка:"]):
                        continue
            
            if not content_text.strip():
                continue

            genai_role = "user" if role == 'user' else "model"
            contents.append(
                types.Content(
                    role=genai_role,
                    parts=[types.Part.from_text(text=content_text)]
                )
            )
            
    # Добавляем актуальный очищенный запрос пользователя
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])
    )

    # Приоритетный список современных моделей для Google GenAI SDK v1
    models_to_try = ['gemini-2.5-flash', 'gemini-1.5-flash']

    for model_name in models_to_try:
        try:
            # Выполняем блокирующий сетевой вызов SDK в пул-потоков, освобождая Event Loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: client_ai.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            )
            if response.text:
                return response.text
        except Exception as e:
            print(f"⚠️ Модель {model_name} недоступна ({e}). Пробую альтернативу...")
            continue

    return "🤖 [SentrySite AI]: Резервные серверы временно перегружены. Попробуйте еще раз."


# --- БЛОК СЕТЕВЫХ ЗАПРОСОВ К ОСНОВНОМУ СЕРВЕРУ ---

async def send_message(content: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """Отправляет запрос на внешний сервер Oylan. При ошибке 402/500 автоматически задействует локальный Gemini."""
    url = f'{BASE_URL}/assistant/{ASSISTANT_ID}/interactions/'
    
    context = ""
    if history:
        for msg in history:
            prefix = 'User' if msg['role'] == 'user' else 'Assistant'
            context += f"{prefix}: {msg['content']}\n"
            
    full_content = context + f'User: {content}' if context else content
    
    # Отправляем параметры в формате строгого JSON-объекта
    payload = {'content': full_content, 'stream': False}
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url, headers=HEADERS, json=payload)
            
            if r.status_code == 402:
                print("⚠️ [Oylan API] Лимиты исчерпаны. Переключаю на резервный Gemini...")
                return await generate_local_response(content, history)
                
            r.raise_for_status()
            res_json = r.json()
            
            if isinstance(res_json, dict):
                if 'response' in res_json and isinstance(res_json['response'], dict):
                    return res_json['response'].get('content', '') or res_json['response'].get('text', '') or ""
                if 'content' in res_json: return res_json['content']
                if 'text' in res_json: return res_json['text']
                if 'reply' in res_json: return res_json['reply']
            return str(res_json)
            
    except Exception as e:
        print(f"⚠️ Сбой внешнего Oylan API ({e}). Локальный каскад Gemini запущен...")
        return await generate_local_response(content, history)


async def fetch_assistants():
    url = f'{BASE_URL}/assistant/'
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=HEADERS, timeout=15.0)
        r.raise_for_status()
        return r.json()


async def create_new_assistant(name: str, model: str = "Oylan"):
    url = f'{BASE_URL}/assistant/'
    payload = {'name': name, 'model': model}
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=HEADERS, json=payload, timeout=15.0)
        r.raise_for_status()
        return r.json()


async def clear_assistant_context(assistant_id: str):
    url = f'{BASE_URL}/assistant/{assistant_id}/contexts/'
    async with httpx.AsyncClient() as client:
        # Используем json= вместо data= для безопасной отработки роутинга на внешнем сервере
        r = await client.delete(url, headers=HEADERS, timeout=15.0)
        r.raise_for_status()
        return {"status": "context cleared", "code": r.status_code}