import os
import httpx
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('OYLAN_API_KEY')
ASSISTANT_ID = os.getenv('OYLAN_ASSISTANT_ID')
BASE_URL = os.getenv('OYLAN_BASE_URL')

# ИСПРАВЛЕНО: Применяем строго специфичный для Oylan формат авторизации 'Api-Key'
HEADERS = {
    'Authorization': f'Api-Key {API_KEY}',
    'accept': 'application/json'
}

# 1. Отправка сообщения с формированием контекста истории из PostgreSQL
async def send_message(content: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """Формирует контекст из истории и нового сообщения, затем отправляет в Oylan API"""
    url = f'{BASE_URL}/assistant/{ASSISTANT_ID}/interactions/'
    
    # Сборка контекста из истории базы данных
    context = ""
    if history:
        for msg in history:
            prefix = 'User' if msg['role'] == 'user' else 'Assistant'
            context += f"{prefix}: {msg['content']}\n"
            
    # Добавляем к накопленному контексту текущее сообщение пользователя
    full_content = context + f'User: {content}' if context else content
    
    # Отправка идет через form-data (параметр data), как указано в спецификации туториала
    data = {
        'content': full_content,
        'stream': False
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=HEADERS, data=data)
        r.raise_for_status()
        return r.json()['response']['content']

# 2. Получить список всех доступных ассистентов
async def fetch_assistants():
    url = f'{BASE_URL}/assistant/'
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=HEADERS, timeout=15.0)
        r.raise_for_status()
        return r.json()

# 3. Создать нового ассистента в системе Oylan
async def create_new_assistant(name: str, model: str = "Oylan"):
    url = f'{BASE_URL}/assistant/'
    payload = {
        'name': name,
        'model': model
    }
    async with httpx.AsyncClient() as client:
        # Передаем как form-data для стабильности интеграции с Oylan Gateway
        r = await client.post(url, headers=HEADERS, data=payload, timeout=15.0)
        r.raise_for_status()
        return r.json()

# 4. Очистить контекст и внутреннюю память ассистента
async def clear_assistant_context(assistant_id: str):
    url = f'{BASE_URL}/assistant/{assistant_id}/contexts/'
    async with httpx.AsyncClient() as client:
        r = await client.delete(url, headers=HEADERS, timeout=15.0)
        r.raise_for_status()
        return {"status": "context cleared", "code": r.status_code}