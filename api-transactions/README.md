# API de Transacciones

API REST básica desarrollada con FastAPI para la gestión de transacciones financieras.

## Características

- ✅ FastAPI como framework web
- ✅ SQLAlchemy como ORM
- ✅ Patrón Repository para acceso a datos
- ✅ Alembic para migraciones de base de datos
- ✅ Configuración mediante variables de entorno (.env)
- ✅ Pruebas unitarias con pytest
- ✅ Estructura de carpetas siguiendo mejores prácticas

## Estructura del Proyecto

```
api-transactions/
├── app/                    # Código de la aplicación
│   ├── models/            # Modelos SQLAlchemy
│   ├── repositories/      # Patrón Repository
│   ├── services/         # Lógica de negocio
│   ├── schemas/          # Schemas Pydantic
│   └── api/              # Endpoints REST
├── alembic/              # Migraciones
├── tests/                # Pruebas unitarias
└── requirements.txt      # Dependencias
```

## Instalación

1. Clonar el repositorio
2. Crear un entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus credenciales de base de datos
```

5. Crear y aplicar migraciones:
```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Uso

### Ejecutar el servidor

```bash
uvicorn app.main:app --reload
```

La API estará disponible en `http://localhost:3000`

### Documentación interactiva

- Swagger UI: `http://localhost:3000/docs`
- ReDoc: `http://localhost:3000/redoc`

## Endpoints

### Transacciones

- `POST /api/v1/transactions/` - Crear transacción
- `GET /api/v1/transactions/` - Listar transacciones
- `GET /api/v1/transactions/{id}` - Obtener transacción
- `PUT /api/v1/transactions/{id}` - Actualizar transacción
- `DELETE /api/v1/transactions/{id}` - Eliminar transacción

## Pruebas

Ejecutar todas las pruebas:
```bash
pytest
```

Ejecutar con cobertura:
```bash
pytest --cov=app tests/
```

## Migraciones

Crear una nueva migración:
```bash
alembic revision --autogenerate -m "Descripción del cambio"
```

Aplicar migraciones:
```bash
alembic upgrade head
```

Revertir última migración:
```bash
alembic downgrade -1
```

## Variables de Entorno

Ver `.env.example` para la lista completa de variables de entorno requeridas.

## Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

