# API Agent

API REST desarrollada con FastAPI para la gestión de conversaciones y chat.

## Verificación de Sintaxis

### Usando pytest (Recomendado)

```bash
pytest --collect-only src/
```

Este comando:
- Intenta importar todos los módulos Python
- Verifica la sintaxis y los imports
- No ejecuta tests, solo verifica que todo se puede importar

### Comando estándar de Python

```bash
python3 -m compileall src/
```

Este comando:
- Compila todos los archivos Python en el directorio `src/`
- Verifica la sintaxis de todos los archivos
- Muestra errores si los hay

Para ver solo errores (sin listar archivos correctos):
```bash
python3 -m compileall -q src/
```

### Otras formas de verificar

#### 1. Usar el script de verificación

```bash
python3 verify_syntax.py
```

#### 2. Verificar un archivo específico

```bash
python3 -m py_compile src/main.py
```

#### 3. Usar ruff (Recomendado)

```bash
# Verificar código (linting)
ruff check src/

# Formatear código automáticamente
ruff format src/

# Verificar y formatear en un solo comando
ruff check src/ && ruff format src/

# Auto-fix problemas que se pueden corregir automáticamente
ruff check --fix src/
```

#### 4. Otras herramientas de linting

```bash
# Con pylint (si está instalado)
pylint src/
```

## Estructura del Proyecto

```
api-agent/
├── src/
│   ├── configuration/     # Configuración de la aplicación
│   ├── common/            # Módulos comunes (entities, repositories, etc.)
│   ├── modules/
│   │   └── conversations/ # Módulo de conversaciones
│   └── main.py            # Punto de entrada de la aplicación
├── requirements.txt       # Dependencias
└── verify_syntax.py      # Script de verificación de sintaxis
```

## Instalación

1. Crear entorno virtual:
```bash
cd api-agent
python3 -m venv .venv
```

2. Activar el entorno virtual:
```bash
# En Linux/Mac/WSL:
source .venv/bin/activate

# En Windows:
.venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
```bash
# Crear archivo .env desde el ejemplo
cp .env.example .env

# Editar .env con tus credenciales (especialmente DATABASE_URL)
nano .env  # o usa tu editor preferido
```

**Variables de entorno requeridas:**
- `DATABASE_URL`: URL de conexión a PostgreSQL (ej: `postgresql://user:password@localhost:5432/agent_db`)
- `OPENAI_API_KEY`: Clave API de OpenAI para el agente de IA (requerida para el chat)
- `API_KEY`: Clave secreta para autenticación (opcional, puede estar vacía)
- `DEBUG`: Modo debug (True/False)
- `HOST`: Host del servidor (por defecto: 0.0.0.0)
- `PORT`: Puerto del servidor (por defecto: 3000)

**Nota:** Una vez activado el entorno virtual, verás `(.venv)` al inicio de tu prompt en la terminal.

## Uso

### Ejecutar el servidor

**Opción 1: Usando Python directamente (recomendado)**
```bash
python src/main.py
```

**Opción 2: Usando uvicorn directamente**
```bash
uvicorn src.main:app --reload --host $(grep HOST .env | cut -d '=' -f2) --port $(grep PORT .env | cut -d '=' -f2)
```

**Nota:** La Opción 1 es la recomendada porque lee automáticamente el puerto y host del archivo `.env`. La Opción 2 requiere que el puerto y host estén en el `.env`.

La API estará disponible en el puerto configurado en tu archivo `.env` (por defecto: `http://localhost:3000`)

### Documentación interactiva

- Swagger UI: `http://localhost:3000/docs`
- ReDoc: `http://localhost:3000/redoc`

## Endpoints

### Conversaciones

- `POST /api/v1/conversations/` - Crear conversación
- `GET /api/v1/conversations/` - Listar conversaciones
- `GET /api/v1/conversations/{id}` - Obtener conversación
- `PUT /api/v1/conversations/{id}` - Actualizar conversación

### Chat

- `POST /api/v1/conversations/chat` - Enviar mensaje de chat

El endpoint de chat utiliza un agente de IA basado en LangGraph y ChatGPT que:
- Mantiene el contexto de la conversación
- Extrae información clave (número de teléfono y monto)
- Valida formato de número (10 dígitos) y que el monto sea mayor a 0
- Solicita confirmación antes de ejecutar la transacción
- Maneja errores de manera conversacional

**Ejemplo de uso:**
```bash
curl -X POST "http://localhost:3000/api/v1/conversations/chat" \
  -H "X-API-Key: your-api-key" \
  -H "X-User-Id: user_123" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hola, quiero enviar dinero"
  }'
```

