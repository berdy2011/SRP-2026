import os
import httpx
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
    'accept': 'application/json'
}

# Инициализация клиента Google GenAI
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
client_ai = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

if not client_ai:
    print("⚠️ Внимание: GEMINI_API_KEY не найден в файле .env")


def generate_local_response(user_msg: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """Генерирует ответ с помощью нового SDK google-genai с жестким вырезанием застрявших тем"""
    if not client_ai:
        return (
            "🤖 [SentrySite AI — Автономный режим]: Реальный ИИ не подключен. "
            "Пожалуйста, добавьте GEMINI_API_KEY в ваш файл .env!"
        )
    
    config = types.GenerateContentConfig(
        system_instruction=(
            "Ты — Oylan AI Assistant, интеллектуальный модуль для системы экологического мониторинга SentrySite AI. "
            "Твой создатель и разработчик — Бердыхан. Ты всегда знаешь, что общаешься именно с ним. "
            "СТРОГОЕ ПРАВИЛО: Отвечай только на то, о чем тебя спросили в текущем сообщении пользователя. "
            "Если пользователь шутит, просит анекдот, здоровается или общается на отвлеченные темы — "
            "отвечай легко, коротко и с юмором. Запрещено самостоятельно упоминать жилые комплексы, "
            "показатели PM2.5, вентиляцию и фильтры HEPA, если пользователь сам прямо не задал технический вопрос про экологию."
        ),
        temperature=0.3
    )

    contents = []
    
    # Список слов-маркеров, которые заставляют модель зацикливаться
    bug_markers = ["жилого комплекса", "жилом комплексе", "hepa", "вентиляции", "pm2.5", "23.5"]
    
    # 1. Защита: Очищаем текущее сообщение пользователя, если в него пролез старый контекст при склейке
    cleaned_user_msg = user_msg
    for marker in bug_markers:
        if marker in cleaned_user_msg.lower() and not any(eco_word in cleaned_user_msg.lower() for eco_word in ["датчик", "качество воздуха", "мониторинг"]):
            # Если пользователь спросил анекдот или "как дела", но там висит хвост про вентиляцию — отрезаем этот хвост
            lines = cleaned_user_msg.split('\n')
            if lines:
                cleaned_user_msg = lines[-1] if "User:" in lines[-1] else lines[0]
                cleaned_user_msg = cleaned_user_msg.replace("User:", "").strip()

    # 2. Защита: Проверяем историю. Если там сидит зацикливание — полностью её игнорируем
    history_is_bugged = False
    if history:
        for msg in history:
            content_str = msg.get('content', '').lower()
            if any(marker in content_str for marker in bug_markers):
                history_is_bugged = True
                break

    if history and not history_is_bugged:
        for msg in history:
            role = "user" if msg['role'] == 'user' else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg['content'])]
                )
            )
    
    # Добавляем очищенное сообщение пользователя
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=cleaned_user_msg)])
    )

    models_to_try = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-flash-8b']

    for model_name in models_to_try:
        try:
            response = client_ai.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            if response.text:
                return response.text
        except Exception as e:
            print(f"⚠️ Модель {model_name} недоступна ({e}). Пробую следующую...")
            continue

    return (
        "🤖 [SentrySite AI]: Все ИИ-модели Google сейчас испытывают высокую нагрузку (ошибка 503).\n"
        "Пожалуйста, подожди пару секунд и отправь сообщение заново!"
    )


# --- БЛОК СЕТЕВЫХ ЗАПРОСОВ К ОСНОВНОМУ СЕРВЕРУ ---

async def send_message(content: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """Отправляет запрос на внешний сервер Oylan. При ошибке 402 автоматически задействует локальный Gemini."""
    url = f'{BASE_URL}/assistant/{ASSISTANT_ID}/interactions/'
    
    # Формируем контекст для внешнего API Oylan
    context = ""
    if history:
        for msg in history:
            prefix = 'User' if msg['role'] == 'user' else 'Assistant'
            context += f"{prefix}: {msg['content']}\n"
            
    full_content = context + f'User: {content}' if context else content
    data = {'content': full_content, 'stream': False}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=HEADERS, data=data)
            
            if r.status_code == 402:
                print("⚠️ [Oylan API] Лимиты исчерпаны (HTTP 402). Подключаю локальный Gemini...")
                # ВАЖНО: передаем чистый content (сообщение пользователя), а не склеенный full_content!
                return generate_local_response(content, history)
                
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
        print(f"⚠️ Сбой внешнего сервера Oylan API ({e}). Переключаю обработку на резервный Gemini AI...")
        # Передаем чистый content
        return generate_local_response(content, history)


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
        r = await client.post(url, headers=HEADERS, data=payload, timeout=15.0)
        r.raise_for_status()
        return r.json()


async def clear_assistant_context(assistant_id: str):
    url = f'{BASE_URL}/assistant/{assistant_id}/contexts/'
    async with httpx.AsyncClient() as client:
        r = await client.delete(url, headers=HEADERS, timeout=15.0)
        r.raise_for_status()
        return {"status": "context cleared", "code": r.status_code}