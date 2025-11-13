#!/usr/bin/env python3
"""
Script to verify that all dependencies are correctly installed and accessible.
"""

import sys
import os

def check_import(module_name, package_name=None):
    """Check if a module can be imported."""
    try:
        __import__(module_name)
        print(f"✅ {package_name or module_name} is installed and importable")
        return True
    except ImportError as e:
        print(f"❌ {package_name or module_name} is NOT importable: {e}")
        return False

def main():
    print("=" * 60)
    print("Verifying Python Environment Setup")
    print("=" * 60)
    print(f"\nPython version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Virtual env: {os.environ.get('VIRTUAL_ENV', 'Not detected')}")
    print(f"\nPython path:")
    for path in sys.path:
        if 'site-packages' in path:
            print(f"  📦 {path}")
    
    print("\n" + "=" * 60)
    print("Checking Dependencies")
    print("=" * 60)
    
    dependencies = [
        ("fastapi", "FastAPI"),
        ("fastapi.middleware.cors", "FastAPI CORS"),
        ("uvicorn", "Uvicorn"),
        ("sqlalchemy", "SQLAlchemy"),
        ("alembic", "Alembic"),
        ("pydantic", "Pydantic"),
        ("pydantic_settings", "Pydantic Settings"),
        ("dotenv", "python-dotenv"),
    ]
    
    results = []
    for module, name in dependencies:
        results.append(check_import(module, name))
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All dependencies are correctly installed!")
        return 0
    else:
        print("❌ Some dependencies are missing. Please run: pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    sys.exit(main())

