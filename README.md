# Local AI Assistant

Локальный AI-ассистент, работающий полностью офлайн: без облаков, без платных API и подписок.

Стек: FastAPI, Ollama, SQLite, FAISS, чистый JavaScript.

---

## Возможности

* Локальная LLM через Ollama (llama3, mistral, phi3 и другие)
* Потоковая генерация ответа (SSE)
* История чата с хранением в SQLite
* Долгосрочная память через FAISS (семантический поиск)
* Вызов инструментов (read_file, write_note, search_memory)
* Веб-интерфейс (одностраничный чат)
* CLI-клиент для работы из терминала
* REST API с документацией OpenAPI

---

## Структура проекта

```
local-ai-assistant/
├── app/
│   ├── api/
│   │   ├── chat.py
│   │   ├── memory.py
│   │   └── sessions.py
│   ├── db/
│   │   └── database.py
│   ├── models/
│   │   └── schemas.py
│   ├── services/
│   │   ├── ollama_service.py
│   │   ├── memory_service.py
│   │   ├── context_builder.py
│   │   └── tool_executor.py
│   └── tools/
│       ├── file_tools.py
│       ├── note_tools.py
│       └── memory_tools.py
├── frontend/
│   └── index.html
├── scripts/
│   └── push_to_github.sh
├── config.py
├── main.py
├── cli.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## Быстрый старт

### 1. Требования

```
python --version        # Python 3.11+

ollama --version        # должен быть установлен
```

Скачать Ollama:
https://ollama.com/download

Загрузить модель:

```
ollama pull llama3
# или
ollama pull mistral
# или
ollama pull phi3
```

---

### 2. Установка

```
git clone https://github.com/<you>/local-ai-assistant.git
cd local-ai-assistant

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
```

---

### 3. Запуск

```
ollama serve &

python main.py
```

Открыть в браузере:
http://localhost:8000

Документация API:
http://localhost:8000/docs

---

### 4. CLI

```
python cli.py chat

python cli.py chat --session work

python cli.py sessions

python cli.py memory list
python cli.py memory add user_name "Alice"
python cli.py memory delete user_name

python cli.py models
```

Команды внутри чата:

| Команда   | Описание               |
| --------- | ---------------------- |
| /quit     | выход                  |
| /clear    | очистка текущей сессии |
| /memory   | просмотр памяти        |
| /sessions | список сессий          |

---

## Конфигурация

Настройки находятся в `.env`:

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
DB_PATH=./data/assistant.db
NOTES_DIR=./data/notes
MAX_CONTEXT_MESSAGES=10
EMBEDDING_MODEL=all-MiniLM-L6-v2
FAISS_INDEX_PATH=./data/faiss_index
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
```

---

## Как работает вызов инструментов

Модель может вернуть специальный блок:

```
<tool_call>
{"name": "read_file", "arguments": {"path": "./data/notes/todo.txt"}}
</tool_call>
```

Дальше происходит:

1. ToolExecutor находит этот блок
2. Выполняет соответствующую функцию
3. Добавляет результат в контекст
4. Повторно вызывает модель

Максимум — 3 итерации на один запрос.

---

### Доступные инструменты

| Инструмент    | Аргументы                | Описание        |
| ------------- | ------------------------ | --------------- |
| read_file     | path: str                | чтение файла    |
| write_note    | text: str, filename: str | запись заметки  |
| search_memory | query: str               | поиск по памяти |

---

## Архитектура памяти

```
Сообщение пользователя
        │
        ▼
ContextBuilder
   ├─ SQLite  → последние сообщения
   └─ FAISS   → релевантные факты
        │
        ▼
Общий контекст → LLM (Ollama)
```

* SQLite хранит историю и факты
* FAISS используется для семантического поиска
* Эмбеддинги — sentence-transformers

---

## API

| Метод  | Endpoint                    | Описание          |
| ------ | --------------------------- | ----------------- |
| POST   | /api/chat                   | обычный ответ     |
| POST   | /api/chat/stream            | потоковый ответ   |
| GET    | /api/sessions               | список сессий     |
| GET    | /api/sessions/{id}/messages | история           |
| DELETE | /api/sessions/{id}          | удаление          |
| GET    | /api/sessions/health/ollama | статус Ollama     |
| GET    | /api/memory                 | список памяти     |
| POST   | /api/memory                 | добавить/обновить |
| DELETE | /api/memory/{key}           | удалить           |

---

## Как выглядит


https://github.com/user-attachments/assets/56a0029f-60d9-476f-8f4b-234c68cff9dd


