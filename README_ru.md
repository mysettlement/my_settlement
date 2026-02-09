<h1 align="center">My Settlement (Моё Поселение)</h1>
<div align="center">

[English](./README.md) | Русский

Многофункциональная текстовая MMORPG для групповых чатов Telegram.
Разработано на Python, Aiogram 3 и SQLAlchemy.

[![GitHub Star](https://img.shields.io/github/stars/mysettlement/my_settlement?style=for-the-badge&labelColor=fae5c0&color=yellow&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz48IS0tIFVwbG9hZGVkIHRvOiBTVkcgUmVwbywgd3d3LnN2Z3JlcG8uY29tLCBHZW5lcmF0b3I6IFNWRyBSZXBvIE1peGVyIFRvb2xzIC0tPgo8c3ZnIHdpZHRoPSI4MDBweCIgaGVpZ2h0PSI4MDBweCIgdmlld0JveD0iMCAwIDM2IDM2IiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiBhcmlhLWhpZGRlbj0idHJ1ZSIgcm9sZT0iaW1nIiBjbGFzcz0iaWNvbmlmeSBpY29uaWZ5LS10d2Vtb2ppIiBwcmVzZXJ2ZUFzcGVjdFJhdGlvPSJ4TWlkWU1pZCBtZWV0Ij48cGF0aCBmaWxsPSIjRkZBQzMzIiBkPSJNMjcuMjg3IDM0LjYyN2MtLjQwNCAwLS44MDYtLjEyNC0xLjE1Mi0uMzcxTDE4IDI4LjQyMmwtOC4xMzUgNS44MzRhMS45NyAxLjk3IDAgMCAxLTIuMzEyLS4wMDhhMS45NzEgMS45NzEgMCAwIDEtLjcyMS0yLjE5NGwzLjAzNC05Ljc5MmwtOC4wNjItNS42ODFhMS45OCAxLjk4IDAgMCAxLS43MDgtMi4yMDNhMS45NzggMS45NzggMCAwIDEgMS44NjYtMS4zNjNMMTIuOTQ3IDEzbDMuMTc5LTkuNTQ5YTEuOTc2IDEuOTc2IDAgMCAxIDMuNzQ5IDBMMjMgMTNsMTAuMDM2LjAxNWExLjk3NSAxLjk3NSAwIDAgMSAxLjE1OSAzLjU2NmwtOC4wNjIgNS42ODFsMy4wMzQgOS43OTJhMS45NyAxLjk3IDAgMCAxLS43MiAyLjE5NGExLjk1NyAxLjk1NyAwIDAgMS0xLjE2LjM3OXoiPjwvcGF0aD48L3N2Zz4=)](https://github.com/mysettlement/my_settlement/stargazers)
![GitHub Repo size](https://img.shields.io/github/repo-size/mysettlement/my_settlement?style=for-the-badge&color=3cb371&labelColor=fae5c0&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz48IS0tIFVwbG9hZGVkIHRvOiBTVkcgUmVwbywgd3d3LnN2Z3JlcG8uY29tLCBHZW5lcmF0b3I6IFNWRyBSZXBvIE1peGVyIFRvb2xzIC0tPg0KPHN2ZyBmaWxsPSIjMDAwMDAwIiB3aWR0aD0iODAwcHgiIGhlaWdodD0iODAwcHgiIHZpZXdCb3g9IjAgMCAzMiAzMiIgdmVyc2lvbj0iMS4xIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPg0KICAgIDxwYXRoIGQ9Ik0xMS45NzUgMTAuODM4bC0wLjAyMS03LjIxOWMtMC4wMDktMC40MDQtMC4zNDQtMC42NDQtMC43NDgtMC42NTRsLTAuNTEzLTAuMDAxYy0wLjQwNS0wLjAwOS0wLjcyNSAwLjM0My0wLjcxNiAwLjc0N2wwLjAyOCA0Ljg1MS04LjMyMS04LjI0MmMtMC4zOTEtMC4zOTEtMS4wMjQtMC4zOTEtMS40MTQgMHMtMC4zOTEgMS4wMjQgMCAxLjQxNGw4LjI4NSA4LjIwNy00LjcyMSAwLjAxMmMtMC40MDQtMC4wMDktMC43NzkgMC4yNy0wLjg0IDAuNzQ2bDAuMDAxIDAuNTEzYzAuMDEwIDAuNDA1IDAuMzQ0IDAuNzM5IDAuNzQ4IDAuNzQ4bDcuMTcyLTAuMDMxYzAuMDA4IDAuMDAxIDAuMDEzIDAuMDAzIDAuMDIwIDAuMDAzbDAuMzY2IDAuMDA4YzAuMjAxIDAuMDA1IDAuMzgzLTAuMDc0IDAuNTEyLTAuMjA1IDAuMTMyLTAuMTMgMC4xNzgtMC4zMTEgMC4xNzUtMC41MTRsLTAuMDQwLTAuMzY2YzAuMDAxLTAuMDA3IDAuMDI3LTAuMDEyIDAuMDI3LTAuMDE5ek0yMC4xODcgMTEuNzM2YzAuMTI5IDAuMTMgMC4zMTEgMC4yMSAwLjUxMiAwLjIwNWwwLjM2Ni0wLjAyOGMwLjAwNyAwIDAuMDEyLTAuMDAyIDAuMDIwLTAuMDA0bDcuMTcyIDAuMDMxYzAuNDA0LTAuMDA5IDAuNzM4LTAuMzQ0IDAuNzQ3LTAuNzQ4bDAuMDAxLTAuNTEzYy0wLjA2MS0wLjQ3Ni0wLjQzNi0wLjc1NS0wLjg0LTAuNzQ2bC00LjcyMS0wLjAxMiA4LjI4NS04LjIwN2MwLjM5MS0wLjM5MSAwLjM5MS0xLjAyNCAwLTEuNDE0cy0xLjAyMy0wLjM5MS0xLjQxNCAwbC04LjMyIDguMjQxIDAuMDI3LTQuODUxYzAuMDA5LTAuNDA0LTAuMzExLTAuNzU2LTAuNzE1LTAuNzQ3bC0wLjUxMyAwLjAwMWMtMC40MDUgMC4wMTAtMC43MzkgMC4yNS0wLjc0OCAwLjY1NGwtMC4wMjEgNy4yMTljMCAwLjAwNyAwLjAyNyAwLjAxMiAwLjAyNyAwLjAyMGwtMC4wNDAgMC4zNjZjLTAuMDA1IDAuMjAzIDAuMDQzIDAuMzg0IDAuMTc0IDAuNTE0ek0xMS44MTMgMjAuMjMyYy0wLjEzLTAuMTMxLTAuMzExLTAuMjEtMC41MTItMC4yMDVsLTAuMzY2IDAuMDA5Yy0wLjAwNyAwLTAuMDEyIDAuMDAzLTAuMDIwIDAuMDAzbC03LjE3My0wLjAzMmMtMC40MDQgMC4wMDktMC43MzggMC4zNDMtMC43NDggMC43NDdsLTAuMDAxIDAuNTE0YzAuMDYyIDAuNDc2IDAuNDM2IDAuNzU1IDAuODQgMC43NDVsNC43MjcgMC4wMTItOC4yOSA4LjIzOGMtMC4zOTEgMC4zOS0wLjM5MSAxLjAyMyAwIDEuNDE0czEuMDI0IDAuMzkgMS40MTQgMGw4LjMyMS04LjI2OC0wLjAyOCA0Ljg3OGMtMC4wMDkgMC40MDQgMC4zMTIgMC43NTYgMC43MTYgMC43NDdsMC41MTMtMC4wMDFjMC40MDUtMC4wMTAgMC43MzktMC4yNSAwLjc0OC0wLjY1NGwwLjAyMS03LjIxOWMwLTAuMDA3LTAuMDI3LTAuMDExLTAuMDI3LTAuMDE5bDAuMDQwLTAuMzk3YzAuMDA1LTAuMjAzLTAuMDQzLTAuMzg0LTAuMTc0LTAuNTE0ek0yMy40MzkgMjIuMDI4bDQuNzI3LTAuMDEyYzAuNDA0IDAuMDA5IDAuNzc5LTAuMjcgMC44NC0wLjc0NWwtMC4wMDEtMC41MTRjLTAuMDEwLTAuNDA0LTAuMzQ0LTAuNzM5LTAuNzQ4LTAuNzQ4aC03LjE3MmMtMC4wMDgtMC0wLjAxMy0wLjAwMy0wLjAyMC0wLjAwM2wtMC40MjgtMC4wMDljLTAuMjAxLTAuMDA2LTAuMzg0IDAuMTM2LTAuNTEyIDAuMjY3LTAuMTMxIDAuMTMtMC4xNzggMC4zMTEtMC4xNzQgMC41MTRsMC4wNDAgMC4zNjZjMCAwLjAwOC0wLjAyNyAwLjAxMi0wLjAyNyAwLjAxOWwwLjAyMSA3LjIxOWMwLjAwOSAwLjQwNCAwLjM0MyAwLjY0NCAwLjc0OCAwLjY1NGwwLjU0NCAwLjAwMWMwLjQwNCAwLjAwOSAwLjcyNS0wLjM0MyAwLjcxNS0wLjc0N2wtMC4wMjctNC44MjkgOC4zNTIgOC4yMmMwLjM5IDAuMzkxIDEuMDIzIDAuMzkxIDEuNDE0IDBzMC4zOTEtMS4wMjMgMC0xLjQxNHoiPjwvcGF0aD4NCjwvc3ZnPg==)
[![GitHub License](https://img.shields.io/github/license/mysettlement/my_settlement?style=for-the-badge&labelColor=fae5c0&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz48IS0tIFVwbG9hZGVkIHRvOiBTVkcgUmVwbywgd3d3LnN2Z3JlcG8uY29tLCBHZW5lcmF0b3I6IFNWRyBSZXBvIE1peGVyIFRvb2xzIC0tPg0KPHN2ZyB3aWR0aD0iODAwcHgiIGhlaWdodD0iODAwcHgiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4NCjxwYXRoIGQ9Ik0xOSAzSDlWM0M3LjExNDM4IDMgNi4xNzE1NyAzIDUuNTg1NzkgMy41ODU3OUM1IDQuMTcxNTcgNSA1LjExNDM4IDUgN1YxMC41VjE3IiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+DQo8cGF0aCBkPSJNMTQgMTdWMTlDMTQgMjAuMTA0NiAxNC44OTU0IDIxIDE2IDIxVjIxQzE3LjEwNDYgMjEgMTggMjAuMTA0NiAxOCAxOVY5VjQuNUMxOCAzLjY3MTU3IDE4LjY3MTYgMyAxOS41IDNWM0MyMC4zMjg0IDMgMjEgMy42NzE1NyAyMSA0LjVWNC41QzIxIDUuMzI4NDMgMjAuMzI4NCA2IDE5LjUgNkgxOC41IiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+DQo8cGF0aCBkPSJNMTYgMjFINUMzLjg5NTQzIDIxIDMgMjAuMTA0NiAzIDE5VjE5QzMgMTcuODk1NCAzLjg5NTQzIDE3IDUgMTdIMTQiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4NCjxwYXRoIGQ9Ik05IDdIMTQiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4NCjxwYXRoIGQ9Ik05IDExSDE0IiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+DQo8L3N2Zz4=)](LICENSE)

</div>

## 🏰 О проекте

**Моё Поселение** — это чат-RPG, где участники группы вместе развивают собственное поселение. Бот анализирует активность чата для генерации ресурсов, позволяя пользователям выбирать профессии, играть в мини-игры и возводить постройки.

Это не просто бот, а проект с собственным [**Игровым движком**](./app/gamer.py), который управляет многоэтапными сценариями, QTE-событиями и игровыми состояниями.

### ✨ Ключевые особенности

* **Модульный игровой движок**: Кастомная OOP-система для обработки интерактивных этапов (Сбор, Охота, QTE).
* **Экономика**: Ресурсы, валюта, крафтинг и торговля.
* **Профессии**: 5 уникальных классов (Землепашец, Знахарь, Ловчий и др.) со специфическими способностями.
* **Трекинг активности**: Интеллектуальный анализ текста (через `wordfreq` и `langdetect`) для награждения за осмысленное общение.
* **Система строительства**: Возведение городских и личных построек для получения бонусов.
* **Асинхронная база данных**: Полностью асинхронные операции с использованием SQLAlchemy и PostgreSQL.

## 🛠️ Технологический стек

* **Фреймворк**: [Aiogram 3.x](https://docs.aiogram.dev/)
* **База данных**: PostgreSQL + SQLAlchemy (Async)
* **Валидация**: Pydantic
* **Анализ текста**: `wordfreq`, `langdetect`, `rapidfuzz`

## 🚀 Быстрый старт

### Требования

* Python 3.10+
* PostgreSQL
* Docker (опционально)

### Локальная установка

```bash
# 1. Клонируйте репозиторий
git clone [https://github.com/mysettlement/my_settlement.git](https://github.com/mysettlement/my_settlement.git)
cd my_settlement

# 2. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
. venv\Scripts\activate  # Windows

# 3. Установите зависимости
pip install -r requirements.txt
```

### Конфигурация

Создайте файл `.env` в корневой директории:

```env
BOT_TOKEN=your_telegram_bot_token
DB_URL=postgresql+asyncpg://user:password@localhost/dbname
ADMIN_IDS=12345678,87654321
DEBUG=True
```

### Запуск

```bash
python main.py
```

## 🐳 Поддержка Docker

Вы можете легко запустить бота с помощью Docker Compose:

```bash
docker-compose up -d --build
```

## 📂 Структура проекта

```Structure
└── 📁my_settlement
    └── 📁app
        ├── __init__.py
        ├── config.py
        ├── core.py
        ├── db.py
        ├── exceptions.py
        ├── gamer.py
        ├── handlers.py
        ├── models.py
        ├── tasks.py
        ├── utils.py
    ├── .dockerignore
    ├── .gitignore
    ├── docker-compose.yml
    ├── Dockerfile
    ├── example.env
    ├── LICENSE
    ├── main.py
    ├── README_ru.md
    ├── README.md
    ├── requirements.in
    ├── requirements.txt
    └── sync_git.ps1
```

## 🤝 Вклад в проект

Мы приветствуем ваш вклад! Не стесняйтесь отправлять Pull Requests.

## 📝 Лицензия

Распространяется под лицензией GNU. Смотрите [LICENSE](./LICENSE) для получения дополнительной информации.

---

Сделано с ❤️ от [megatocha](https://github.com/megatocha)
