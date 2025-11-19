# Agent Transactional Chat

Sistema de chatbot conversacional para realizar transacciones financieras mediante lenguaje natural.

## 🏗️ Arquitectura

El proyecto está compuesto por tres servicios principales:

- **`api-agent`**: Servicio de agente conversacional que procesa mensajes del usuario usando LangChain/LangGraph y OpenAI
- **`api-transactions`**: Servicio de gestión de transacciones financieras
- **`chat-front`**: Interfaz web del chat (React + TypeScript + Vite)

Los servicios se comunican mediante **RabbitMQ** para procesar transacciones de forma asíncrona.

## 🚀 Inicio Rápido

### Prerrequisitos

- Python 3.11+
- Node.js 18+
- Docker y Docker Compose
- PostgreSQL
- RabbitMQ
- Redis
- Clave API de OpenAI

### Configuración

1. **Clonar el repositorio**
```bash
git clone <repository-url>
cd agent-transactional-chat
```

2. **Configurar variables de entorno**

Crea archivos `.env` en cada servicio con las configuraciones necesarias (ver ejemplos en cada directorio).

3. **Iniciar servicios de infraestructura**

```bash
cd api-transactions
docker-compose up -d
```

4. **Ejecutar migraciones y crear tablas**

Antes de iniciar los servicios, es necesario ejecutar las migraciones de base de datos para crear las tablas necesarias.

**Opción 1: Usar el script de migraciones (Recomendado)**

Desde la raíz del proyecto, puedes usar el script de migraciones:

```bash
# Ejecutar migraciones para todos los servicios
./run_migrations.sh

# Ejecutar migraciones para un servicio específico
./run_migrations.sh api-agent
./run_migrations.sh api-transactions

# Esperar antes de ejecutar (útil si la BD tarda en estar lista)
./run_migrations.sh all 5
```

**Opción 2: Ejecutar manualmente**

**Para API Agent:**
```bash
cd api-agent
# Activar el entorno virtual (si usas uno)
source .venv/bin/activate  # En Linux/Mac
# o
.venv\Scripts\activate  # En Windows

# Ejecutar migraciones
alembic upgrade head
```

**Para API Transactions:**
```bash
cd api-transactions
# Activar el entorno virtual (si usas uno)
source .venv/bin/activate  # En Linux/Mac
# o
.venv\Scripts\activate  # En Windows

# Ejecutar migraciones
alembic upgrade head
```

**Nota:** Si encuentras errores con las migraciones (por ejemplo, versión incorrecta en la base de datos), puedes verificar el estado actual con:
```bash
alembic current    # Ver versión actual
alembic history    # Ver historial de migraciones
```

Las migraciones crearán automáticamente las siguientes tablas:
- **api-agent**: `users`, `conversations`, `messages`
- **api-transactions**: `transactions`

5. **Iniciar API Agent**
```bash
cd api-agent
# Asegúrate de tener el entorno virtual activado
uvicorn src.main:app --reload
```

6. **Iniciar API Transactions**
```bash
cd api-transactions
# Asegúrate de tener el entorno virtual activado
uvicorn src.main:app --reload
```

7. **Iniciar Frontend**
```bash
cd chat-front
npm install
npm run dev
```

## 📋 Características

- ✅ Chat conversacional en español
- ✅ Procesamiento de transacciones mediante lenguaje natural
- ✅ Validación de datos (montos, números de teléfono)
- ✅ Gestión de conversaciones y mensajes
- ✅ Autenticación con JWT
- ✅ Comunicación asíncrona entre servicios
- ✅ Documentación interactiva (Swagger UI)

## 🗄️ Migraciones de Base de Datos

El proyecto utiliza **Alembic** para gestionar las migraciones de base de datos. Las migraciones crean automáticamente todas las tablas necesarias.

### Comandos de Migración

**Verificar estado actual:**
```bash
alembic current    # Ver versión actual aplicada
alembic history    # Ver historial de migraciones
```

**Aplicar migraciones:**
```bash
alembic upgrade head    # Aplicar todas las migraciones pendientes
```

**Revertir migraciones:**
```bash
alembic downgrade -1    # Revertir la última migración
alembic downgrade base  # Revertir todas las migraciones
```

**Crear nueva migración:**
```bash
alembic revision --autogenerate -m "Descripción de la migración"
```

### Tablas Creadas

**api-agent:**
- `users` - Usuarios del sistema
- `conversations` - Conversaciones del chat
- `messages` - Mensajes de las conversaciones

**api-transactions:**
- `transactions` - Transacciones financieras

### Solución de Problemas

Si encuentras errores como "Can't locate revision identified by 'XXX'", significa que la base de datos tiene una versión de migración que no existe en los archivos. Puedes corregirlo:

1. Verificar la versión actual: `alembic current`
2. Si la versión es incorrecta, actualizar manualmente la tabla `alembic_version` en la base de datos
3. O usar: `alembic stamp head` para marcar la versión actual sin ejecutar migraciones

## 🛠️ Tecnologías

- **Backend**: FastAPI, SQLAlchemy, Alembic
- **Agente IA**: LangChain, LangGraph, OpenAI
- **Mensajería**: RabbitMQ
- **Caché**: Redis
- **Base de datos**: PostgreSQL
- **Frontend**: React, TypeScript, Vite, TailwindCSS

## 📚 Documentación

Cada servicio expone documentación interactiva en:
- API Agent: `http://localhost:8000/docs`
- API Transactions: `http://localhost:3000/docs`

## 📝 Licencia

MIT

