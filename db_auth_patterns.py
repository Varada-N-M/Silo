# ============================================================
# DATABASE (SQLAlchemy + Alembic) & AUTH (JWT) KNOWLEDGE BASE
# ============================================================

DATABASE_KNOWLEDGE = [
    # ── Async Session ─────────────────────────────────────
    {
        "id": "db_async_session",
        "category": "database",
        "title": "SQLAlchemy async session setup",
        "content": """
# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,  # e.g. "postgresql+asyncpg://user:pass@localhost/db"
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    \"\"\"FastAPI dependency — yields an async DB session.\"\"\"
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
""",
    },
    # ── SQLAlchemy Models ─────────────────────────────────
    {
        "id": "db_sqlalchemy_models",
        "category": "database",
        "title": "SQLAlchemy ORM models with relationships",
        "content": """
# app/models/user.py
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id:         Mapped[int]  = mapped_column(primary_key=True, index=True)
    email:      Mapped[str]  = mapped_column(String, unique=True, index=True, nullable=False)
    full_name:  Mapped[str]  = mapped_column(String, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active:  Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["Item"]] = relationship("Item", back_populates="owner")

# app/models/item.py
from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Item(Base):
    __tablename__ = "items"

    id:          Mapped[int]   = mapped_column(primary_key=True, index=True)
    title:       Mapped[str]   = mapped_column(String, nullable=False)
    description: Mapped[str]   = mapped_column(String, nullable=True)
    price:       Mapped[float] = mapped_column(Float, nullable=False)
    owner_id:    Mapped[int]   = mapped_column(ForeignKey("users.id"), nullable=False)

    owner: Mapped["User"] = relationship("User", back_populates="items")
""",
    },
    # ── Generic CRUD ──────────────────────────────────────
    {
        "id": "db_generic_crud",
        "category": "database",
        "title": "Generic async CRUD base class for SQLAlchemy",
        "content": """
# app/crud/base.py
from typing import Generic, TypeVar, Type, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> ModelType | None:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 20) -> list[ModelType]:
        result = await db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, obj_in: CreateSchemaType, **kwargs) -> ModelType:
        data = obj_in.model_dump()
        data.update(kwargs)
        db_obj = self.model(**data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, db_obj: ModelType, obj_in: UpdateSchemaType | dict) -> ModelType:
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, id: Any) -> None:
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.flush()

# Usage:
# from app.crud.base import CRUDBase
# from app.models.item import Item
# from app.schemas.item import ItemCreate, ItemUpdate
# class CRUDItem(CRUDBase[Item, ItemCreate, ItemUpdate]): pass
# item = CRUDItem(Item)
""",
    },
    # ── Alembic ───────────────────────────────────────────
    {
        "id": "db_alembic_setup",
        "category": "migrations",
        "title": "Alembic migration setup and common commands",
        "content": """
# Setup Alembic for async SQLAlchemy:
# 1. pip install alembic asyncpg
# 2. alembic init alembic

# alembic/env.py — key changes for async:
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.db.base import Base       # import your Base
from app.models import user, item  # import all models so Base knows them
from app.core.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata

async def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

# Common Alembic commands:
# alembic revision --autogenerate -m "create users table"
# alembic upgrade head
# alembic downgrade -1
# alembic history
""",
    },
]

AUTH_KNOWLEDGE = [
    # ── JWT Auth ──────────────────────────────────────────
    {
        "id": "auth_jwt_security",
        "category": "auth",
        "title": "FastAPI JWT authentication — security.py",
        "content": """
# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None
""",
    },
    # ── Auth Dependency ───────────────────────────────────
    {
        "id": "auth_dependency",
        "category": "auth",
        "title": "FastAPI get_current_user dependency",
        "content": """
# app/core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.security import decode_access_token
from app.crud.user import user as crud_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception
    user = await crud_user.get(db, id=int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    return user

async def get_current_superuser(current_user=Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user
""",
    },
    # ── Auth Endpoints ────────────────────────────────────
    {
        "id": "auth_endpoints",
        "category": "auth",
        "title": "FastAPI login and register endpoints",
        "content": """
# app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.auth import Token, UserRegister
from app.schemas.user import UserRead
from app.crud.user import user as crud_user
from app.core.security import verify_password, create_access_token, get_password_hash

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await crud_user.get_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserRead, status_code=201)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await crud_user.get_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = get_password_hash(user_in.password)
    user = await crud_user.create(db, obj_in=user_in, hashed_password=hashed)
    return user
""",
    },
    # ── NextAuth ──────────────────────────────────────────
    {
        "id": "auth_nextauth_credentials",
        "category": "auth",
        "title": "NextAuth.js credentials provider with FastAPI backend",
        "content": """
// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const res = await fetch(`${process.env.API_URL}/api/v1/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            username: credentials?.email ?? "",
            password: credentials?.password ?? "",
          }),
        });

        if (!res.ok) return null;
        const data = await res.json();

        return { id: "user", accessToken: data.access_token };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) token.accessToken = (user as any).accessToken;
      return token;
    },
    async session({ session, token }) {
      (session as any).accessToken = token.accessToken;
      return session;
    },
  },
  pages: { signIn: "/login" },
  session: { strategy: "jwt" },
});

export { handler as GET, handler as POST };
""",
    },
]