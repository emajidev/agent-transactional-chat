# Prompt.md

## Prompt 1

```
create a basic REST API in FastAPI using .env and separate folders with best practices, use the repository pattern with SQLAlchemy ORM and for migrations use Alembic. Also, for each prompt create a Prompt.md that records the prompts made as well as the context used. The repo must include unit tests
```

### Context Used

Files created:

- `requirements.txt`
- `.env.example`
- `alembic.ini`
- `pytest.ini`
- `README.md`
- `app/__init__.py`
- `app/main.py`
- `app/config.py`
- `app/database.py`
- `app/models/__init__.py`
- `app/models/transaction.py`
- `app/repositories/__init__.py`
- `app/repositories/transaction_repository.py`
- `app/schemas/__init__.py`
- `app/schemas/transaction.py`
- `app/services/__init__.py`
- `app/services/transaction_service.py`
- `app/api/__init__.py`
- `app/api/v1/__init__.py`
- `app/api/v1/routes/__init__.py`
- `app/api/v1/routes/transactions.py`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/.gitkeep`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_transactions.py`
- `Prompt.md`

## Prompt 2

```
the api folder should not exist, the following folders should exist:

common ->dtos,
guards, 
helpers, 
repositories, 
services, 
utils, 
interceptors, 
errors, 
enums, 
entities
configuration

migrations

modules -> transactions -> dtos, repositories, services , entities, transactions.controller.py , transactions.service.py
```

### Context Used

Files created/modified:

- `common/__init__.py`
- `common/dtos/__init__.py`
- `common/guards/__init__.py`
- `common/helpers/__init__.py`
- `common/repositories/__init__.py`
- `common/repositories/database.py`
- `common/services/__init__.py`
- `common/utils/__init__.py`
- `common/interceptors/__init__.py`
- `common/errors/__init__.py`
- `common/enums/__init__.py`
- `common/enums/transaction_type.py`
- `common/entities/__init__.py`
- `configuration/__init__.py`
- `configuration/config.py`
- `modules/__init__.py`
- `modules/transactions/__init__.py`
- `modules/transactions/dtos/__init__.py`
- `modules/transactions/dtos/transaction.py`
- `modules/transactions/repositories/__init__.py`
- `modules/transactions/repositories/transaction_repository.py`
- `modules/transactions/services/__init__.py`
- `modules/transactions/services/transactions.service.py`
- `modules/transactions/entities/__init__.py`
- `modules/transactions/entities/transaction.py`
- `modules/transactions/transactions.controller.py`
- `app/main.py` (modified)
- `alembic/env.py` (modified)
- `tests/conftest.py` (modified)
- `tests/test_transactions.py` (modified)

## Prompt 3

```
id, conversation_id, transaction_id, recipient_phone, amount, currency, status (Enum pending/completed/failed), error_message, timestamps @transaction.entity.py
```

