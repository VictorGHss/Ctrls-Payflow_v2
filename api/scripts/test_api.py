#!/bin/bash
# Script para rodar API FastAPI localmente
# Execute no diretório api/

#!/usr/bin/env python
"""
Script de teste da API PayFlow
"""

import sys
import time

import requests


def wait_for_api(timeout=30):
    """Aguarda a API ficar pronta"""
    start = time.time()

    while time.time() - start < timeout:
        try:
            response = requests.get("http://localhost:8000/healthz", timeout=2)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)

    return False


if __name__ == "__main__":
    print("Aguardando API iniciar...")

    if wait_for_api():
        print("✅ API pronta em http://localhost:8000")
        print("")
        print("Acesse:")
        print("  - Swagger: http://localhost:8000/docs")
        print("  - ReDoc: http://localhost:8000/redoc")
        print("  - Health: http://localhost:8000/healthz")
        sys.exit(0)
    else:
        print("❌ API não respondeu em tempo")
        sys.exit(1)
