# Vkusnie Cookies for Idealo.de

Сборщик свежих валидных куки для обхода защиты Akamai + reCAPTCHA на сайте idealo.de.

Проект автоматически:
- запускает браузер через Playwright
- ловит 429 (капчу)
- решает reCAPTCHA через RuCaptcha
- проходит форму (если требуется)
- собирает куки
- сохраняет их в базу данных

Полученные куки можно использовать в обычных HTTP-запросах (например, через curl_cffi, requests или httpx), чтобы избежать 429 и капчи при сборе данных по EAN-кодам товаров.

## Для чего это нужно

На странице поиска idealo.de[](https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q=...) стоит защита Akamai.  
При частых запросах или подозрительном поведении сервер возвращает 429 - показывает reCAPTCHA.  
После успешного прохождения капчи браузер получает нормальные куки, с которыми обычные запросы работают без ограничений (по крайней мере какое-то время).

Этот сервис держит пул свежих куки, чтобы клиенты могли их быстро брать через API.

## Технологии

- **Backend**: FastAPI + Uvicorn
- **Браузер**: Playwright (chromium, async)
- **Капча**: RuCaptcha (python-rucaptcha)
- **База данных**: PostgreSQL
- **Прокси**: пул HTTP-прокси с авторизацией

## Структура проекта
```
vkusnie-cookies-for-idealo-de/
├── api/                    # FastAPI-сервер (эндпоинты /latest-cookie, /random-cookie)
│   ├── main.py
│   ├── models.py
│   ├── config.py
│   └── start.sh
├── cookie_collector/       # сборщик куки (Playwright + RuCaptcha)
│   ├── cookie_collector.py
│   ├── config.py
│   └── start.sh
├── .env                    # ключи RuCaptcha, прокси и настройки
├── .env.example
└── README.md
```


## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/minorytanaka/vkusnie-cookies-for-idealo-de.git
cd vkusnie-cookies-for-idealo-de
```

### 2. Установить зависимости
```
uv sync
```

### 3. Настроить .env
Скопируй .env.example ->.env и заполни:
```
# Обязательно
RUCAPTCHA_API_KEY=ваш_ключ_от_rucaptcha

# Прокси 
PROXY_POOL=["http://login:password@host:port", "http://login:password@host:port"]

# Сколько браузеров одновременно запускать для сбора куков
NUM_BROWSERS=5

HEADLESS=False  # True для безголового режима
DB_URL=postgresql://postgres:secretpassword@localhost:5432/cookies
```
### 4. Запустить PostgreSQL (либо без докера)
Создай папку в корне проекта vkusnie_postgres_data
```
docker run --name vkusnie-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=secretpassword \
  -e POSTGRES_DB=cookies \
  -d -p 5432:5432 \
  -v ~/vkusnie_postgres_data:/var/lib/postgresql/data \
  postgres:latest
```
### 5. Запустить сборщик куки
```
cd cookie_collector
sh start.sh
```

### 6. Запустить API
```
cd ../api
sh start.sh
```

API будет доступно по адресу:
http://localhost:8000/docs (Swagger)

Основные эндпоинты:
- GET /latest-cookie - самая свежая кука
- GET /random-cookie - случайная
