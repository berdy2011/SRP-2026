import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('OYLAN_API_KEY')
ASSISTANT_ID = os.getenv('OYLAN_ASSISTANT_ID')
BASE_URL = os.getenv('OYLAN_BASE_URL')

HEADERS = {
    'Authorization': f'Api-Key {API_KEY}',
    'accept': 'application/json'
}

# 1. Отправка сообщения
async def send_message(content: str) -> str:
    url = f'{BASE_URL}/assistant/{ASSISTANT_ID}/interactions/'
    payload = {'content': content}
    
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=HEADERS, data=payload, timeout=30.0)
        r.raise_for_status()
        res_json = r.json()
        return res_json['response']['content']

# 2. Получить список ассистентов (Эту функцию искал main.py)
async def fetch_assistants():
    url = f'{BASE_URL}/assistant/'
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=HEADERS, timeout=15.0)
        r.raise_for_status()
        return r.json()

# 3. Создать нового ассистента
async def create_new_assistant(name: str, model: str = "Oylan"):
    url = f'{BASE_URL}/assistant/'
    payload = {
        'name': name,
        'model': model
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=HEADERS, data=payload, timeout=15.0)
        r.raise_for_status()
        return r.json()

# 4. Очистить контекст ассистента
async def clear_assistant_context(assistant_id: str):
    url = f'{BASE_URL}/assistant/{assistant_id}/contexts/'
    async with httpx.AsyncClient() as client:
        r = await client.delete(url, headers=HEADERS, timeout=15.0)
        r.raise_for_status()
        return {"status": "context cleared", "code": r.status_code}