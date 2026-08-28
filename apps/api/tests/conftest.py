import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://openlivery:openlivery@localhost:5432/openlivery_test",
)
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("SEED_ENABLED", "false")

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


test_engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)


SELLER_PASSWORD = "contrasena-segura"


@pytest.fixture
def login(client: TestClient):
    """Switch the shared TestClient's session to another user."""
    def _login(email: str, password: str = SELLER_PASSWORD) -> None:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
    return _login


@pytest.fixture
def create_seller(client: TestClient):
    """Add a seller to the current agency (requires a superadmin session)."""
    def _create(name: str, email: str, role: str = "seller") -> dict:
        response = client.post(
            "/api/agency/users",
            json={"name": name, "email": email, "password": SELLER_PASSWORD, "role": role},
        )
        assert response.status_code == 201, response.text
        return response.json()
    return _create


@pytest.fixture
def db_session():
    """A session onto the test database, for arranging rows the API has no
    endpoint to create (usage records) or asserting on stored state."""
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "agency_name": "Agencia Prisma",
            "name": "Ana Admin",
            "email": "ana@prisma.com",
            "password": "contrasena-segura",
        },
    )
    assert response.status_code == 201
    return client
