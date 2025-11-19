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

4. **Iniciar API Agent**
```bash
cd api-agent
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

5. **Iniciar API Transactions**
```bash
cd api-transactions
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

6. **Iniciar Frontend**
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

