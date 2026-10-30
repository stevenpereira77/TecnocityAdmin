from sqlalchemy import text

from app.config import AppSettings
from app.database.engine import create_database_engine, create_session_factory
from app.database.session import session_scope


def test_sqlite_engine_and_transaction_scope(tmp_path):
    settings = AppSettings.load()
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_database_engine(db_url)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        assert session.execute(text("select 1")).scalar_one() == 1

    engine.dispose()
    assert settings.app_name == "Tecnocity Admin"
