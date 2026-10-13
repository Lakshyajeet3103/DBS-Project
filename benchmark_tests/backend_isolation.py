"""Optional pytest plugin for inherited backend tests; never uses the product DB.

Run: python -m pytest --noconftest -p benchmark_tests.backend_isolation <test paths>
"""
import os
from pathlib import Path
import sys
import tempfile
import pytest


def pytest_configure(config):
    if 'database.connection' in sys.modules:
        raise pytest.UsageError('Backend DB imported before isolation was configured')
    parent = Path(__file__).resolve().parents[1]/'data/vector_store/person4-tests'
    parent.mkdir(parents=True, exist_ok=True)
    config._benchmark_db = tempfile.TemporaryDirectory(prefix='inherited-', dir=parent)
    settings = {'DATABASE_URL': 'sqlite:///'+(Path(config._benchmark_db.name)/'suite.db').as_posix(),
                'ENVIRONMENT': 'development', 'PYTHON_DOTENV_DISABLED': '1',
                'CORS_ORIGINS': 'http://localhost:5173,http://127.0.0.1:5173',
                'SESSION_DURATION_DAYS': '7'}
    config._benchmark_old_env = {key: os.environ.get(key) for key in settings}
    os.environ.update(settings)


def pytest_sessionstart(session):
    from database.seed import seed_database
    seed_database()


def pytest_unconfigure(config):
    if hasattr(config, '_benchmark_db'):
        connection = sys.modules.get('database.connection')
        if connection:
            connection.engine.dispose()
        config._benchmark_db.cleanup()
    for key, value in getattr(config, '_benchmark_old_env', {}).items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
