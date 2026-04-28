import os

import pytest
from fastapi.testclient import TestClient

# Force in-memory repository + mock WhatsApp provider for all tests regardless
# of the surrounding environment.
os.environ.setdefault("REPOSITORY_TYPE", "memory")
os.environ.setdefault("WHATSAPP_PROVIDER", "mock")

from app.main import create_app  # noqa: E402
from app.repositories import get_repository  # noqa: E402
from app.repositories.memory import InMemoryRepository  # noqa: E402
from app.repositories.memory import repository as legacy_repository  # noqa: E402
from app.services.whatsapp import get_provider, reset_provider_cache  # noqa: E402
from app.services.whatsapp.mock import MockWhatsAppProvider  # noqa: E402


@pytest.fixture(autouse=True)
def reset_repository() -> InMemoryRepository:
    """Reset both repository singletons used in the codebase.

    `app.repositories.__init__._repo` is the instance the FastAPI app sees;
    `app.repositories.memory.repository` is the legacy module-level instance
    referenced by some helpers and by older tests. Tests that need to inspect
    state should accept this fixture to get the live repo.
    """
    legacy_repository.reset()
    repo = get_repository()
    if isinstance(repo, InMemoryRepository):
        repo.reset()
        return repo
    return legacy_repository


@pytest.fixture(autouse=True)
def mock_whatsapp() -> MockWhatsAppProvider:
    reset_provider_cache()
    provider = get_provider()
    assert isinstance(provider, MockWhatsAppProvider)
    provider.reset()
    return provider


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def auth_headers(user_id: str, name: str | None = None, phone: str | None = None) -> dict[str, str]:
    return {
        "x-demo-user-id": user_id,
        "x-demo-name": name or user_id,
        "x-demo-phone": phone or "+966500000000",
    }
