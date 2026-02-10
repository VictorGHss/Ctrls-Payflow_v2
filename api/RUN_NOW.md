# 🚀 Rodar Agora - Comandos Exatos

## Windows PowerShell

```powershell
# 1. Abra PowerShell como administrador
# 2. Vá para a pasta do projeto
cd C:\Projeto\ctrls-payflow-v2\api

# 3. Criar virtual environment
python -m venv .venv

# 4. Ativar venv
.\.venv\Scripts\Activate.ps1

# 5. Atualizar pip
python -m pip install --upgrade pip

# 6. Instalar dependências
pip install -r requirements.txt

# 7. Rodar API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Em outro PowerShell (para testes)

```powershell
cd C:\Projeto\ctrls-payflow-v2\api
.\.venv\Scripts\Activate.ps1

# Rodar testes
pytest tests/ -v

# Ou com coverage
pytest tests/ --cov=app --cov-report=html
```

## Acessar

- **Swagger**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/healthz
- **Ready**: http://localhost:8000/ready

## Docker

```bash
# Build
docker-compose build

# Run
docker-compose up -d

# Logs
docker-compose logs -f

# Stop
docker-compose down
```

## Troubleshooting

### Erro: Python não encontrado
```powershell
# Verificar se Python está instalado
python --version

# Se não: instale de https://www.python.org/downloads/
```

### Erro: pip não encontrado
```powershell
# Tentar:
python -m pip install --upgrade pip

# Depois:
python -m pip install -r requirements.txt
```

### Erro: Porta 8000 já em uso
```powershell
# Usar outra porta:
uvicorn app.main:app --reload --port 8001
```

---

**Status**: ✅ Pronto para rodar!

