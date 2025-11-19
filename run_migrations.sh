#!/bin/bash
# Script para ejecutar migraciones de base de datos para los servicios del proyecto
#
# Uso:
#   ./run_migrations.sh [api-agent|api-transactions|all] [wait_seconds]

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}⏳ $1${NC}"
}

# Función para ejecutar migraciones en un servicio
run_migrations_for_service() {
    local service=$1
    local wait_seconds=${2:-0}
    local service_path="$(pwd)/$service"
    
    if [ ! -d "$service_path" ]; then
        print_error "El directorio $service no existe"
        return 1
    fi
    
    if [ ! -f "$service_path/alembic.ini" ]; then
        print_error "No se encontró alembic.ini en $service"
        return 1
    fi
    
    print_header "Ejecutando migraciones para $service"
    
    if [ "$wait_seconds" -gt 0 ]; then
        print_info "Esperando $wait_seconds segundos..."
        sleep "$wait_seconds"
    fi
    
    cd "$service_path"
    
    # Activar entorno virtual si existe
    if [ -d ".venv" ]; then
        if [ -f ".venv/bin/activate" ]; then
            source .venv/bin/activate
        elif [ -f ".venv/Scripts/activate" ]; then
            source .venv/Scripts/activate
        fi
    fi
    
    # Ejecutar migraciones
    local migration_output
    migration_output=$(alembic upgrade head 2>&1) || {
        # Si falla por versión incorrecta, corregirla
        if echo "$migration_output" | grep -q "Can't locate revision"; then
            print_info "Versión incorrecta detectada, corrigiendo..."
            # Obtener la versión head disponible desde los archivos de migración
            local head_version=$(ls -1 alembic/versions/*.py 2>/dev/null | grep -v __init__ | sort | tail -1 | xargs grep -h "revision:" | head -1 | sed "s/.*revision.*=.*['\"]\([^'\"]*\)['\"].*/\1/" || echo "")
            if [ -n "$head_version" ]; then
                # Actualizar directamente la tabla alembic_version usando Python inline
                python3 << EOF
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from sqlalchemy import text
from src.configuration.config import get_engine

try:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num = :version"), {"version": "$head_version"})
        conn.commit()
        print("✓ Versión actualizada a $head_version")
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
EOF
                # Reintentar migraciones
                if alembic upgrade head 2>&1; then
                    print_success "Migraciones completadas para $service"
                    cd - > /dev/null
                    return 0
                fi
            fi
        fi
        echo "$migration_output"
        print_error "Error al ejecutar migraciones para $service"
        cd - > /dev/null
        return 1
    }
    
    print_success "Migraciones completadas para $service"
    cd - > /dev/null
    return 0
}

# Determinar qué servicios ejecutar
SERVICE=${1:-all}
WAIT_SECONDS=${2:-0}

# Validar argumentos
if [ "$SERVICE" != "all" ] && [ "$SERVICE" != "api-agent" ] && [ "$SERVICE" != "api-transactions" ]; then
    print_error "Servicio inválido: $SERVICE"
    echo "Uso: $0 [api-agent|api-transactions|all] [wait_seconds]"
    exit 1
fi

# Ejecutar migraciones
SUCCESS=true

if [ "$SERVICE" == "all" ]; then
    SERVICES=("api-agent" "api-transactions")
else
    SERVICES=("$SERVICE")
fi

for service in "${SERVICES[@]}"; do
    if ! run_migrations_for_service "$service" "$WAIT_SECONDS"; then
        SUCCESS=false
    fi
done

# Resultado final
echo ""
print_header "Resultado"
if [ "$SUCCESS" = true ]; then
    print_success "Todas las migraciones se ejecutaron correctamente"
    exit 0
else
    print_error "Algunas migraciones fallaron"
    exit 1
fi
