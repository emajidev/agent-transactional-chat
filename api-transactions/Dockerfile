# Usar imagen base de Python 3.12 slim
FROM python:3.12-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivo de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY src/ ./src/

# Exponer el puerto 3000
EXPOSE 3000

# Variables de entorno por defecto (pueden ser sobrescritas)
ENV HOST=0.0.0.0
ENV PORT=3000
ENV DEBUG=False

# Comando para ejecutar la aplicación
CMD ["python", "-m", "src.main"]

