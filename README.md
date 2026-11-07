# simple_crm

Простая CRM с канбан-доской задач. Backend: Python + FastAPI + SQLite. Frontend: Vue 3 + Vite.

## Возможности

- Канбан-доска: К выполнению / В работе / На проверке / Готово
- Клиенты с отдельным таймлайном; задачу можно привязать к клиенту
- Роли, команды и права на постановку задач между командами
- Комментарии, результаты, таймлайн событий по задаче
- Автоматизация: по расписанию, при смене статуса, при отсутствии активности по клиенту
- Интеграция с почтой (SMTP) и отправка писем из задачи
- Realtime-уведомления по WebSocket
- Админка: пользователи, команды, права, автоматизация, почта

При первом запуске создаются аккаунты `user1`..`user5` / `password1`..`password5` (`user1` — админ).

## Запуск в Docker (рекомендуется)

```bash
cp .env.example .env
docker compose up --build
```

Открыть http://localhost:8080

Данные SQLite и аватары хранятся в volume `crm_data`.

## Локальный запуск без Docker

```bash
./start.sh
```

Или по отдельности:

```bash
# backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173 · Backend: http://localhost:8000
