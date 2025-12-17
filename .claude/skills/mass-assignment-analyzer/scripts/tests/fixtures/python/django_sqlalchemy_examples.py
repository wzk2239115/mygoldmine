"""
Python Test Fixtures - Mass Assignment Vulnerabilities
"""
from django.db import models
from django.http import JsonResponse
from django.views import View
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.exc import SQLAlchemyError

# Django ORM Examples
class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    is_admin = models.BooleanField(default=False)

    class Meta:
        app_label = 'users'


class DjangoUserView(View):
    # VULNERABLE: create() with request.POST
    def create_user(self, request):
        user = User.objects.create(**request.POST.dict())
        return JsonResponse({'id': user.id})

    # VULNERABLE: get_or_create with all request data
    def get_or_create_user(self, request):
        user, created = User.objects.get_or_create(**request.POST.dict())
        return JsonResponse({'created': created})

    # VULNERABLE: update_or_create with request data
    def update_or_create_user(self, request):
        user, created = User.objects.update_or_create(
            id=request.POST.get('id'),
            defaults=request.POST.dict()
        )
        return JsonResponse({'created': created})

    # VULNERABLE: Direct property assignment in loop
    def bulk_update(self, request):
        users_data = request.POST.getlist('users')
        for user_data in users_data:
            user = User(id=user_data['id'])
            for key, value in user_data.items():
                setattr(user, key, value)
            user.save()

    # SAFE: Explicitly set allowed fields
    def create_user_safe(self, request):
        user = User.objects.create(
            name=request.POST.get('name'),
            email=request.POST.get('email')
        )
        return JsonResponse({'id': user.id})


# SQLAlchemy Examples
Base = declarative_base()


class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    price = Column(String)
    admin_only = Column(String)


class SQLAlchemyExample:
    def __init__(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)

    # VULNERABLE: session.add() with **kwargs
    def create_product(self, session: Session, data: dict):
        product = Product(**data)
        session.add(product)
        session.commit()
        return product

    # VULNERABLE: Direct instantiation with user data
    def create_from_request(self, session: Session, request_data: dict):
        product = Product(**request_data)
        session.add(product)
        session.commit()
        return product

    # SAFE: Explicitly set fields
    def create_product_safe(self, session: Session, data: dict):
        product = Product(
            name=data.get('name'),
            price=data.get('price')
        )
        session.add(product)
        session.commit()
        return product


# Pydantic Examples
try:
    from pydantic import BaseModel

    class UserModel(BaseModel):
        name: str
        email: str
        is_admin: bool = False

    # VULNERABLE: parse_obj with user data
    def parse_user_data(data: dict):
        user = UserModel.parse_obj(data)
        return user

    # VULNERABLE: construct with untrusted data
    def construct_user_unsafe(data: dict):
        user = UserModel.construct(**data)
        return user
except ImportError:
    pass
