# Форум — лабораторная 2

HTTP API для тем форума. Поля темы: `id`, `title`, `author`, `status` (`open` или `closed`). Идентификатор назначает сервер. Данные хранятся в памяти и исчезают после перезапуска.

Стек: Python, FastAPI, Pydantic, Uvicorn, SQLAlchemy, SQLite.

Первый этап лабы 2: подготовлено подключение к SQLite через SQLAlchemy. API тем пока использует память. Таблицы и сохранение тем будут добавлены на следующих этапах.

## Запуск

Нужны Python 3.10+ и Git. Откройте папку проекта в VS Code и выполните в PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

При первой настройке скопируйте пример настроек в `.env`:

```powershell
Copy-Item .env.example .env
```

Если `.env` уже существует, используйте его и добавьте `DATABASE_URL` из `.env.example`.

Запустите сервис из корня проекта:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Остановка сервера — `Ctrl+C`.


## Подключение к базе данных

В `.env.example` указана строка подключения для локальной SQLite:

```dotenv
DATABASE_URL=sqlite:///./forum.db
```

Настройка читается из переменной окружения `DATABASE_URL` или файла `.env` в корне проекта.
Переменная окружения имеет приоритет над файлом. Если настройка не задана, модуль базы данных
выдаёт понятную ошибку. Путь `./forum.db` считается относительно папки запуска, поэтому
выполняйте команды из корня проекта.

Проверка подключения:

```powershell
python -c "from app.database import SessionLocal; db = SessionLocal(); print(db.connection().exec_driver_sql('SELECT 1').scalar()); db.close()"
```

Ожидаемый результат — `1`. При первом подключении появляется файл `forum.db`.
На этом этапе таблиц в нём ещё нет.

Файлы `.env` и `forum.db` уже исключены из Git через `.gitignore`.
В репозиторий добавляется только пример настроек `.env.example`.

## Эндпоинты

| Метод  | Путь               | Результат                |
| ------ | ------------------ | ------------------------ |
| GET    | `/health`          | 200, `{"status":"ok"}`   |
| POST   | `/api/topics`      | 201, созданная тема с id |
| GET    | `/api/topics`      | 200, массив тем          |
| GET    | `/api/topics/{id}` | 200 или 404              |
| PATCH  | `/api/topics/{id}` | 200 или 404              |
| DELETE | `/api/topics/{id}` | 204 без тела или 404     |
| GET    | `/docs`            | Swagger UI               |
| GET    | `/openapi.json`    | Спецификация OpenAPI     |

Заголовок обязателен: 1–200 символов, автор: 1–100. Статус по умолчанию — `open`. Неверные данные и сломанный JSON возвращают 400 в формате `{"error":"текст","field":"поле"}`.

Фильтры и пагинация: `/api/topics?author=Иван&status=open&limit=10&offset=0`. `limit`: 1–100, `offset`: от 0. Каждый запрос записывается в лог: метод, путь, статус, время в миллисекундах.

## Проверка

Откройте http://localhost:8000/docs и выполняйте запросы через **Try it out → Execute**. Примеры запросов находятся в `requests.http`.

Для backcheck откройте второй терминал в папке проекта:

```powershell
.\.venv\Scripts\Activate.ps1
$env:NO_PROXY = "localhost,127.0.0.1,::1"
python -m backcheck --lab 1 --stars
```

Контракт заполнен в `contract.json`. Знаки `?` у README, Swagger и логов означают ручную проверку на сдаче.

Сдача: PR из ветки `lab-2` в `main`.
