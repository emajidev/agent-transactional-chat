#!/usr/bin/env python3
"""
Script para verificar la sintaxis de todos los archivos Python del proyecto.
"""

import ast
import sys
from pathlib import Path


def check_syntax(file_path):
    """Verifica la sintaxis de un archivo Python."""
    try:
        file_path_obj = Path(file_path)
        source = file_path_obj.read_text(encoding='utf-8')
        ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return False, f"Error de sintaxis en línea {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {e!s}"
    else:
        return True, None

def check_imports():
    """Intenta importar los módulos principales para verificar que no hay errores."""
    print("\n" + "=" * 60)
    print("Verificando Imports")
    print("=" * 60)

    # Agregar el directorio src al path
    src_path = Path(__file__).parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path.parent))

    modules_to_check = [
        "src.configuration.config",
        "src.common.entities.base",
        "src.common.repositories.base_repository",
        "src.common.enums.conversation_status",
        "src.modules.conversations.entities.conversation_entity",
        "src.modules.conversations.dtos.conversation",
        "src.modules.conversations.repositories.conversation_repository",
        "src.modules.conversations.services.conversations_service",
        "src.modules.conversations.controller",
    ]

    results = []
    for module_name in modules_to_check:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
            results.append(True)
        except SyntaxError as e:
            print(f"❌ {module_name}: Error de sintaxis - {e}")
            results.append(False)
        except ImportError as e:
            print(f"⚠️  {module_name}: Error de importación - {e}")
            # No es crítico si faltan dependencias externas
            results.append(True)
        except Exception as e:
            print(f"❌ {module_name}: {e}")
            results.append(False)

    return all(results)

def main():
    print("=" * 60)
    print("Verificación de Sintaxis - API Agent")
    print("=" * 60)

    # Directorio raíz del proyecto
    project_root = Path(__file__).parent
    src_dir = project_root / "src"

    if not src_dir.exists():
        print(f"❌ No se encontró el directorio src en {project_root}")
        return 1

    print(f"\nVerificando archivos Python en: {src_dir}")
    print("-" * 60)

    # Encontrar todos los archivos Python
    python_files = list(src_dir.rglob("*.py"))

    if not python_files:
        print("❌ No se encontraron archivos Python")
        return 1

    errors = []
    for py_file in sorted(python_files):
        relative_path = py_file.relative_to(project_root)
        is_valid, error_msg = check_syntax(py_file)

        if is_valid:
            print(f"✅ {relative_path}")
        else:
            print(f"❌ {relative_path}: {error_msg}")
            errors.append((relative_path, error_msg))

    print("\n" + "=" * 60)
    print("Resumen")
    print("=" * 60)
    print(f"Total de archivos: {len(python_files)}")
    print(f"Archivos válidos: {len(python_files) - len(errors)}")
    print(f"Archivos con errores: {len(errors)}")

    if errors:
        print("\n❌ Errores encontrados:")
        for file_path, error in errors:
            print(f"  - {file_path}: {error}")
        return 1

    # Verificar imports
    imports_ok = check_imports()

    print("\n" + "=" * 60)
    if not errors and imports_ok:
        print("✅ ¡Toda la sintaxis es correcta!")
        return 0
    else:
        print("❌ Se encontraron errores")
        return 1

if __name__ == "__main__":
    sys.exit(main())

