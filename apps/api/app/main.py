from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .config import get_settings
from .database import Base, SessionLocal, engine
from .models import Agency, User
from .security import hash_password
from .slugs import unique_slug
from .routers import (
    agency,
    agent_tools,
    agents,
    auth,
    catalog,
    clients,
    conversations,
    dashboard,
    domains,
    meta_channels,
    meta_webhook,
    portal,
    providers,
    whatsapp,
    whatsapp_cloud,
    whatsapp_cloud_webhook,
    widget,
)


def seed_superadmin():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        email = "admin@nexacore.com.mx"
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            agency = db.scalar(select(Agency).where(Agency.name == "NexaCore"))
            if not agency:
                agency = Agency(name="NexaCore", slug=unique_slug(db, Agency, "slug", "NexaCore"))
                db.add(agency)
                db.flush()
            user = User(
                agency_id=agency.id,
                name="Admin NexaCore",
                email=email,
                password_hash=hash_password("prueba123"),
                role="superadmin",
            )
            db.add(user)
            db.commit()
            print(f"✅ Initial superadmin user '{email}' created successfully.")
        else:
            user.role = "superadmin"
            user.password_hash = hash_password("prueba123")
            db.commit()
            print(f"✅ Superadmin password and role updated for '{email}'.")
    except Exception as e:
        db.rollback()
        print(f"⚠️ Error seeding superadmin: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_superadmin()
    yield


settings = get_settings()
app = FastAPI(
    title="NexaCoreAgentManager API",
    description="API to manage agencies, clients and AI agents.",
    version="0.3.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    # The configured frontend origin (a real domain in production) plus any
    # localhost/127.0.0.1 port, so changing WEB_PORT never breaks local dev.
    allow_origins=[settings.frontend_url],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api")
app.include_router(agency.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(agent_tools.router, prefix="/api")
app.include_router(providers.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(portal.router, prefix="/api")
app.include_router(whatsapp.router, prefix="/api")
app.include_router(whatsapp.internal_router, prefix="/api")
app.include_router(whatsapp_cloud.router, prefix="/api")
app.include_router(whatsapp_cloud_webhook.public_router, prefix="/api")
app.include_router(meta_channels.router, prefix="/api")
app.include_router(meta_webhook.public_router, prefix="/api")
app.include_router(widget.router, prefix="/api")
app.include_router(domains.public_router, prefix="/api")
