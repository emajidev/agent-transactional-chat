import importlib.util
from pathlib import Path

base_repo_file = Path(__file__).parent / "base.repository.py"
spec = importlib.util.spec_from_file_location("base_repository", base_repo_file)
if spec is None or spec.loader is None:
    raise ImportError(f"Cannot load module from {base_repo_file}")
base_repository = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base_repository)

Base = base_repository.Base
get_db = base_repository.get_db
get_engine = base_repository.get_engine
get_session = base_repository.get_session
session_context_var = base_repository.session_context_var
transaction = base_repository.transaction
transactional = base_repository.transactional
BaseRepository = base_repository.BaseRepository
BasePostgresRepository = base_repository.BasePostgresRepository
ModelType = base_repository.ModelType

__all__ = [
    "Base",
    "get_db",
    "get_engine",
    "get_session",
    "session_context_var",
    "transaction",
    "transactional",
    "BaseRepository",
    "BasePostgresRepository",
    "ModelType",
]

