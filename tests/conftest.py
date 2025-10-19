import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:  # pragma: no cover - optional dependency guard
    import dotenv  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    sys.modules["dotenv"] = SimpleNamespace(load_dotenv=lambda *args, **kwargs: None)


def _ensure_alembic_stub() -> None:
    if "alembic" in sys.modules:
        return

    command_module = ModuleType("alembic.command")

    def upgrade(cfg, revision):  # pragma: no cover - stub
        from app.services.database import get_engine
        from sqlmodel import SQLModel

        SQLModel.metadata.create_all(get_engine())

    command_module.upgrade = upgrade

    config_module = ModuleType("alembic.config")

    class Config:  # pragma: no cover - stub
        def __init__(self, config_file):
            self.config_file_name = config_file
            self._options: dict[str, str] = {}

        def set_main_option(self, key: str, value: str) -> None:
            self._options[key] = value

    config_module.Config = Config

    alembic_module = ModuleType("alembic")
    alembic_module.command = command_module
    alembic_module.config = config_module

    sys.modules["alembic"] = alembic_module
    sys.modules["alembic.command"] = command_module
    sys.modules["alembic.config"] = config_module


_ensure_alembic_stub()

from sqlmodel import SQLModel

from app import create_app
from app.services.database import get_engine


@pytest.fixture()
def app(monkeypatch):
    database_name = f"test_{uuid4().hex}.db"
    monkeypatch.setenv("DATABASE_NAME", database_name)
    monkeypatch.setenv("LOGGING_CONFIG", "")

    app = create_app("development")
    app.config.update(TESTING=True)

    templates_path = PROJECT_ROOT / "templates"
    if app.jinja_loader and str(templates_path) not in app.jinja_loader.searchpath:
        app.jinja_loader.searchpath.insert(0, str(templates_path))

    with app.app_context():
        SQLModel.metadata.create_all(get_engine())

    yield app

    db_path = Path(app.config["DATABASE_PATH"])
    if db_path.exists():
        db_path.unlink()


@pytest.fixture()
def client(app):
    return app.test_client()
