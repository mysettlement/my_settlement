import ast
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from fastapi import FastAPI
from wtforms import TextAreaField, ValidationError

import app.db as app_db
from app.config import settings
from app.models import (
    User, Settlement, Settler, Resource, 
    Profession, BuildingType, Building
)

class PythonListField(TextAreaField):
    """
    Поле, которое позволяет редактировать Python-списки как текст.
    При сохранении преобразует строку "['a', 'b']" обратно в реальный список ['a', 'b'].
    """
    def process_formdata(self, valuelist):
        if valuelist and valuelist[0]:
            try:
                self.data = ast.literal_eval(valuelist[0])
                if not isinstance(self.data, list):
                    raise ValueError("Должен быть список")
            except (ValueError, SyntaxError):
                raise ValidationError("Введите корректный Python-список, например: ['😀', '😎']")
        else:
            self.data = []

    def _value(self):
        return str(self.data) if self.data is not None else "[]"

# === 1. Аутентификация ===
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        valid_user = getattr(settings, "ADMIN_USERNAME", "admin")
        valid_pass = getattr(settings, "ADMIN_PASSWORD", "admin")

        if username == valid_user and password == valid_pass:
            request.session.update({"token": "valid_token"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "token" in request.session


# === 2. Представления Моделей ===

class UserAdmin(ModelView, model=User):
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"
    
    column_list = [User.id, User.telegram_id, User.name, User.language, User.timezone]
    column_searchable_list = [User.id, User.telegram_id, User.name]
    column_sortable_list = [User.id, User.telegram_id, User.name, User.language, User.timezone]
    
    column_labels = {
        User.telegram_id: "Telegram ID",
        User.name: "Имя",
        User.language: "Язык",
        User.timezone: "Часовой пояс"
    }

class SettlementAdmin(ModelView, model=Settlement):
    name = "Поселение"
    name_plural = "Поселения"
    icon = "fa-solid fa-city"
    
    column_list = [Settlement.id, Settlement.name, Settlement.owner, Settlement.created_at, Settlement.member_count]
    column_sortable_list = [Settlement.id, Settlement.name, Settlement.owner, Settlement.created_at]
    column_searchable_list = [Settlement.name, Settlement.chat_id]
    
    column_labels = {
        Settlement.chat_id: "ID чата",
        Settlement.name: "Название",
        Settlement.owner: "Правитель",
        Settlement.created_at: "Создано",
        Settlement.member_count: "Жители"
    }

class SettlerAdmin(ModelView, model=Settler):
    name = "Поселенец"
    name_plural = "Поселенцы"
    icon = "fa-solid fa-users"
    
    column_list = [
        Settler.id, Settler.user, Settler.settlement, 
        Settler.level, Settler.rank, Settler.profession
    ]
    column_sortable_list = [
        Settler.id, Settler.user, Settler.settlement, 
        Settler.level, Settler.rank, Settler.profession
    ]
    column_searchable_list = ["Пользователь", "Поселение"]
    
    column_labels = {
        Settler.user: "Пользователь",
        Settler.settlement: "Поселение",
        Settler.level: "Уровень",
        Settler.rank: "Титул",
        Settler.profession: "Профессия"
    }

    form_overrides = {
        "rank_emoji_available": PythonListField,
        "special_emoji_available": PythonListField
    }

    def search_query(self, stmt, term):
        stmt = stmt.outerjoin(Settler.user).outerjoin(Settler.settlement)
        
        stmt = stmt.filter(
            or_(
                User.name.ilike(f"%{term}%"),
                Settlement.name.ilike(f"%{term}%")
            )
        )
        return stmt

class ResourceAdmin(ModelView, model=Resource):
    name = "Ресурс"
    name_plural = "Ресурсы"
    icon = "fa-solid fa-box-open"
    
    column_list = [Resource.id, Resource.emoji, Resource.name, Resource.rarity, Resource.category]
    column_searchable_list = [Resource.name]
    column_sortable_list = [Resource.category, Resource.rarity, Resource.name]

    column_labels = {
        Resource.emoji: "Эмодзи",
        Resource.name: "Название",
        Resource.rarity: "Редкость",
        Resource.category: "Категория"
    }

class ProfessionAdmin(ModelView, model=Profession):
    name = "Профессия"
    name_plural = "Профессии"
    icon = "fa-solid fa-hammer"
    
    column_list = [Profession.id, Profession.emoji, Profession.name, Profession.required_level]
    column_searchable_list = [Profession.name]
    column_sortable_list = [Profession.id, Profession.name, Profession.required_level]

    column_labels = {
        Profession.emoji: "Эмодзи",
        Profession.name: "Название",
        Profession.required_level: "Требуемый уровень"
    }

class BuildingTypeAdmin(ModelView, model=BuildingType):
    name = "Чертеж"
    name_plural = "Чертежи"
    icon = "fa-solid fa-scroll"
    
    column_list = [BuildingType.id, BuildingType.emoji, BuildingType.name, BuildingType.max_level, BuildingType.is_private]
    column_searchable_list = [BuildingType.name]
    column_sortable_list = [BuildingType.id, BuildingType.name, BuildingType.max_level, BuildingType.is_private]
    
    form_columns = [
        BuildingType.name, BuildingType.emoji, BuildingType.description,
        BuildingType.is_private, BuildingType.max_level, BuildingType.construction_time,
        BuildingType.required_professions, BuildingType.bonuses, "costs"
    ]

    column_labels = {
        BuildingType.emoji: "Эмодзи",
        BuildingType.name: "Название",
        BuildingType.max_level: "Макс. уровень",
        BuildingType.is_private: "Приватный"
    }

class BuildingAdmin(ModelView, model=Building):
    name = "Постройка"
    name_plural = "Постройки"
    icon = "fa-solid fa-building"
    
    column_list = [Building.id, Building.type, Building.settlement, Building.level, "status"]
    column_searchable_list = [BuildingType.name]
    column_sortable_list = [Building.id, Building.type, Building.settlement, Building.level, "status"]

    column_labels = {
        Building.type: "Чертеж",
        Building.settlement: "Поселение",
        Building.level: "Уровень",
        "status": "Статус"
    }
    
    column_formatters = {
        "status": lambda b, a: "✅ Готово" if b.is_ready else "⏳ Стройка"
    }

    def search_query(self, stmt, term):
        stmt = stmt.outerjoin(Settler.settlement)
        
        stmt = stmt.filter(
            Settlement.name.ilike(f"%{term}%")
        )
        return stmt


# === 3. Функция инициализации ===

def setup_panel(app: FastAPI, db_engine=None):
    authentication_backend = AdminAuth(secret_key=settings.BOT_TOKEN) 
    
    admin = Admin(
        app=app, 
        engine=db_engine or app_db.engine, 
        authentication_backend=authentication_backend,
        title="My Settlement! - Admin Panel"
    )

    admin.add_view(UserAdmin)
    admin.add_view(SettlementAdmin)
    admin.add_view(SettlerAdmin)
    admin.add_view(ResourceAdmin)
    admin.add_view(ProfessionAdmin)
    admin.add_view(BuildingTypeAdmin)
    admin.add_view(BuildingAdmin)
    
    return admin
