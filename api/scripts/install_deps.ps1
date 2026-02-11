# Script para instalar dependências no Windows PowerShell

Write-Host "Instalando dependências..." -ForegroundColor Green

# Atualizar pip
python -m pip install --upgrade pip

# Instalar dependências do requirements.txt
python -m pip install `
  fastapi==0.104.1 `
  uvicorn==0.24.0 `
  sqlalchemy==2.0.23 `
  pydantic==2.5.0 `
  pydantic-settings==2.1.0 `
  python-dotenv==1.0.0 `
  cryptography==41.0.7 `
  httpx==0.25.2 `
  tenacity==8.2.3 `
  python-multipart==0.0.6 `
  pytest==7.4.3 `
  pytest-cov==4.1.0 `
  pytest-asyncio==0.21.1 `
  black==23.12.1 `
  ruff==0.1.11 `
  mypy==1.7.1 `
  ipython==8.18.1

Write-Host "✅ Todas as dependências instaladas!" -ForegroundColor Green

