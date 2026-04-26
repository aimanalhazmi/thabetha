import os

import pytest
from fastapi.testclient import TestClient

# Force in-memory repository for all tests regardless of environment
os.environ.setdefault("REPOSITORY_TYPE", "memory")

from app.main import create_app  # noqa: E402
from app.repositories.memory import repository  # noqa: E402


@pytest.fixture(autouse=True)
def reset_repository() -> None:
    repository.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def auth_headers(user_id: str, name: str | None = None, phone: str | None = None) -> dict[str, str]:
    return {
        "x-demo-user-id": user_id,
        "x-demo-name": name or user_id,
        "x-demo-phone": phone or "+966500000000",
    }
