# ============================================================
# FASTAPI PATTERNS & SNIPPETS KNOWLEDGE BASE
# ============================================================

FASTAPI_KNOWLEDGE = [
    # ── Project Structure ──────────────────────────────────
    {
        "id": "fastapi_project_structure",
        "category": "project_structure",
        "title": "FastAPI Recommended Project Structure",
        "content": """
FastAPI recommended project structure for scalable applications:

my_project/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── core/
│   │   ├── config.py        # Settings via pydantic BaseSettings
│   │   ├── security.py      # JWT / password hashing
│   │   └── dependencies.py  # Shared FastAPI dependencies
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── users.py
│   │   │   │   ├── auth.py
│   │   │   │   └── items.py
│   │   │   └── router.py    # Aggregates all v1 routes
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── crud/                # DB operations (Create/Read/Update/Delete)
│   └── db/
│       ├── base.py          # SQLAlchemy Base
│       └── session.py       # DB engine & session factory
├── alembic/                 # DB migrations
├── tests/
├── .env
└── requirements.txt
""",
    },
    # ── main.py ───────────────────────────────────────────
    {
        "id": "fastapi_main",
        "category": "boilerplate",
        "title": "FastAPI main.py entry point",
        "content": """
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,  # e.g. ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {"status": "ok"}
""",
    },
    # ── Config ────────────────────────────────────────────
    {
        "id": "fastapi_config",
        "category": "config",
        "title": "FastAPI settings with pydantic-settings",
        "content": """
# app/core/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "My App"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "changeme-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/dbname"

    class Config:
        env_file = ".env"

settings = Settings()
""",
    },
    # ── Router ────────────────────────────────────────────
    {
        "id": "fastapi_router",
        "category": "routing",
        "title": "FastAPI APIRouter aggregator",
        "content": """
# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, items

api_router = APIRouter()
api_router.include_router(auth.router,  prefix="/auth",  tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
""",
    },
    # ── CRUD Endpoint ─────────────────────────────────────
    {
        "id": "fastapi_crud_endpoint",
        "category": "endpoints",
        "title": "FastAPI CRUD endpoint example (items)",
        "content": """
# app/api/v1/endpoints/items.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.crud import item as crud_item
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=list[ItemRead])
async def list_items(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud_item.get_multi(db, skip=skip, limit=limit)

@router.post("/", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(
    item_in: ItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud_item.create(db, obj_in=item_in, owner_id=current_user.id)

@router.get("/{item_id}", response_model=ItemRead)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await crud_item.get(db, id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.put("/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: int,
    item_in: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await crud_item.get(db, id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return await crud_item.update(db, db_obj=item, obj_in=item_in)

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await crud_item.get(db, id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await crud_item.remove(db, id=item_id)
""",
    },
    # ── Pydantic Schema ───────────────────────────────────
    {
        "id": "fastapi_pydantic_schema",
        "category": "schemas",
        "title": "Pydantic v2 schemas for request/response",
        "content": """
# app/schemas/item.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ItemBase(BaseModel):
    title: str
    description: Optional[str] = None
    price: float

class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None

class ItemRead(ItemBase):
    id: int
    owner_id: int
    created_at: datetime

    model_config = {"from_attributes": True}  # replaces orm_mode in pydantic v2
""",
    },
    # ── Background Tasks ──────────────────────────────────
    {
        "id": "fastapi_background_tasks",
        "category": "async",
        "title": "FastAPI Background Tasks",
        "content": """
# Using BackgroundTasks for fire-and-forget operations
from fastapi import BackgroundTasks, APIRouter

router = APIRouter()

def send_welcome_email(email: str, name: str):
    # Heavy operation runs after response is sent
    print(f"Sending welcome email to {email}")

@router.post("/register")
async def register_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    user = await crud_user.create(db, obj_in=user_data)
    background_tasks.add_task(send_welcome_email, user.email, user.name)
    return user  # Response is sent immediately; email runs after
""",
    },
    # ── Exception Handlers ────────────────────────────────
    {
        "id": "fastapi_exception_handlers",
        "category": "error_handling",
        "title": "FastAPI global exception handlers",
        "content": """
# app/main.py — add custom exception handlers
from fastapi import Request
from fastapi.responses import JSONResponse

class AppException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# Usage in endpoint:
# raise AppException(status_code=403, detail="Not enough permissions")
""",
    },
]