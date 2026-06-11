from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
@app.get("/health")
def health():
    return {"status": "ok", "project": "SentrySite AI"}
class SiteRequest(BaseModel):
    lat: float
    lon: float
    object_type: str

# Тестовые данные PM2.5 по городам
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

@app.post("/chat")
def chat(request: SiteRequest):
    pm25, city = get_pm25(request.lat, request.lon)
    safe = pm25 <= 5

    return {
        "status": "ok",
        "city": city,
        "location": f"{request.lat}, {request.lon}",
        "object": request.object_type,
        "pm25": pm25,
        "who_limit": 5,
        "safe": safe,
        "message": "Безопасно ✅" if safe else f"Опасно! PM2.5 = {pm25} мкг/м³ — выше нормы ВОЗ в {round(pm25/5, 1)}x ❌"
    }