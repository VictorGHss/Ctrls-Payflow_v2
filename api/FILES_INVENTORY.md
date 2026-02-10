# Inventário de Arquivos - PayFlow API

## 📁 Estrutura Completa

```
api/
│
├── 📄 README.md                          # Guia completo (Setup, Docker, Deployment)
├── 📄 ARCHITECTURE.md                    # Visão arquitetural detalhada
├── 📄 PAYLOADS.md                        # Exemplos de payloads JSON
├── 📄 .gitignore                         # Arquivos ignorados no Git
├── 📄 .env.example                       # Template de variáveis de ambiente
├── 📄 requirements.txt                   # Dependências Python
├── 📄 pyproject.toml                     # Config: pytest, black, ruff
├── 📄 Dockerfile                         # Multi-stage Docker build
├── 📄 docker-compose.yml                 # Orquestração: api, worker, cloudflared
├── 📄 Makefile                           # Comandos auxiliares
├── 📄 .vscode-settings.json              # Settings para VSCode/PyCharm
│
├── 📂 app/                               # Pacote principal
│   ├── __init__.py                       # Package init
│   ├── main.py                           # FastAPI app (rotas, middleware)
│   ├── config.py                         # Pydantic Settings (variáveis env)
│   ├── crypto.py                         # Criptografia (Fernet/AES)
│   ├── logging.py                        # Logging com redação de dados sensíveis
│   ├── database.py                       # SQLAlchemy models + init
│   ├── conta_azul_client.py              # HTTP client com retry/rate-limit
│   ├── email_service.py                  # SMTP email com TLS
│   ├── payment_processor.py              # Lógica de negócio (processamento de recibos)
│   ├── routes_health.py                  # Rotas: /healthz, /ready
│   ├── routes_oauth.py                   # Rotas: OAuth2 flow
│   └── worker.py                         # Worker loop (polling periódico)
│
├── 📂 tests/                             # Suite de testes
│   ├── __init__.py
│   ├── conftest.py                       # Fixtures pytest
│   ├── test_crypto.py                    # Testes: encrypt/decrypt
│   ├── test_idempotency.py               # Testes: idempotência, checkpoints
│   └── test_email.py                     # Testes: email mockado, payloads
│
├── 📂 scripts/                           # Scripts utilitários
│   ├── __init__.py
│   ├── generate_key.py                   # Gera MASTER_KEY segura
│   ├── manage.py                         # CLI: create-test, reset
│   └── test_oauth.py                     # Testa fluxo OAuth interativamente
│
└── 📂 data/                              # (criado em runtime)
    └── payflow.db                        # SQLite database
```

## 📋 Arquivos por Função

### 🔧 Configuração & Setup

| Arquivo | Descrição |
|---------|-----------|
| `.env.example` | Template com todas as variáveis obrigatórias |
| `config.py` | Pydantic Settings, validação automática |
| `pyproject.toml` | Pytest, Black, Ruff configurados |
| `requirements.txt` | Todas as dependências Python |

### 🚀 Inicialização

| Arquivo | Descrição |
|---------|-----------|
| `main.py` | FastAPI app, middleware de segurança |
| `worker.py` | Loop de polling (background job) |
| `Dockerfile` | Build multi-stage, usuário não-root |
| `docker-compose.yml` | 3 serviços: api, worker, cloudflared |

### 🔐 Segurança & Dados

| Arquivo | Descrição |
|---------|-----------|
| `crypto.py` | Criptografia Fernet/AES para tokens |
| `logging.py` | Redação de dados sensíveis em logs |
| `database.py` | Models SQLAlchemy, inicialização |

### 📡 Integração Externa

| Arquivo | Descrição |
|---------|-----------|
| `routes_oauth.py` | OAuth2: authorize, callback, token refresh |
| `conta_azul_client.py` | HTTP client com backoff/rate-limit |
| `email_service.py` | SMTP TLS para envio de recibos |

### 💼 Lógica de Negócio

| Arquivo | Descrição |
|---------|-----------|
| `payment_processor.py` | Orquestra: tokens → parcelas → emails |
| `payment_processor.py` | `DoctorFallbackResolver`: email do médico |
| `payment_processor.py` | Idempotência via `sent_receipts` |

### 🔗 Rotas HTTP

| Arquivo | Descrição |
|---------|-----------|
| `routes_health.py` | `/healthz`, `/ready`, `/` |
| `routes_oauth.py` | `/oauth/authorize`, `/oauth/callback` |

### ✅ Testes

| Arquivo | Descrição |
|---------|-----------|
| `test_crypto.py` | Encrypt/decrypt, caracteres especiais |
| `test_idempotency.py` | Duplicate detection, checkpoints |
| `test_email.py` | Email mockado, MIME multipart |
| `conftest.py` | Fixtures compartilhadas |

### 🛠️ Scripts Auxiliares

| Arquivo | Descrição |
|---------|-----------|
| `generate_key.py` | Gera MASTER_KEY (32 bytes base64) |
| `manage.py` | create-test, reset de banco |
| `test_oauth.py` | Teste interativo do fluxo OAuth |

## 📊 Linhas de Código

| Módulo | LOC | Descrição |
|--------|-----|-----------|
| `main.py` | ~60 | FastAPI app |
| `config.py` | ~80 | Pydantic Settings |
| `database.py` | ~150 | SQLAlchemy models |
| `payment_processor.py` | ~350 | Lógica de negócio |
| `conta_azul_client.py` | ~150 | HTTP client |
| `routes_oauth.py` | ~250 | OAuth flow |
| `email_service.py` | ~120 | SMTP email |
| `crypto.py` | ~70 | Fernet crypto |
| `logging.py` | ~100 | Logging com redação |
| `worker.py` | ~80 | Polling loop |
| **TOTAL** | **~1,400** | **Code** |
| Tests | ~500 | pytest suite |
| Docs | ~1,500 | README, ARCHITECTURE, PAYLOADS |

## 🚀 Como Usar Cada Arquivo

### Para iniciar a API localmente:

```bash
# Ativar venv
.\.venv\Scripts\activate

# Config
cp .env.example .env
# Editar .env com valores reais

# Rodar
python app/main.py  # ou: uvicorn app.main:app --reload
```

### Para rodar testes:

```bash
pytest tests/ -v
pytest tests/test_crypto.py::test_encrypt_decrypt -v
```

### Para gerar MASTER_KEY:

```bash
python scripts/generate_key.py
```

### Para criar conta de teste:

```bash
python scripts/manage.py create-test
```

### Para testar OAuth:

```bash
python scripts/test_oauth.py
```

### Para rodar via Docker:

```bash
docker-compose up -d
docker-compose logs -f api
docker-compose logs -f worker
```

## 📝 Dependências

Instaladas via `requirements.txt`:

### Web Framework
- `fastapi==0.104.1` - Web API
- `uvicorn==0.24.0` - ASGI server

### Database
- `sqlalchemy==2.0.23` - ORM
- `python-dotenv==1.0.0` - .env loader

### Configuration
- `pydantic==2.5.0` - Data validation
- `pydantic-settings==2.1.0` - Settings management

### Security
- `cryptography==41.0.7` - Fernet encryption

### HTTP
- `httpx==0.25.2` - Async HTTP client

### Testing
- `pytest==7.4.3` - Test framework
- `pytest-cov==4.1.0` - Coverage
- `pytest-asyncio==0.21.1` - Async tests

### Code Quality
- `black==23.12.1` - Code formatter
- `ruff==0.1.11` - Linter
- `mypy==1.7.1` - Type checker

## 🔄 Fluxo de Desenvolvimento

```
1. Clonar repositório
   └─ git clone ...

2. Setup local
   ├─ python -m venv .venv
   ├─ pip install -r requirements.txt
   ├─ cp .env.example .env
   └─ python scripts/generate_key.py

3. Desenvolvimento
   ├─ Editar código em app/
   ├─ Rodar testes: pytest
   ├─ Lint: ruff check
   └─ Format: black app/

4. Commit & Push
   └─ git add . && git commit && git push

5. CI/CD (GitHub Actions, etc)
   ├─ Run tests
   ├─ Lint check
   └─ Build Docker image

6. Deploy
   └─ docker-compose up -d
```

---

**Total de arquivos**: 28  
**Linhas de código**: ~1,400  
**Linhas de testes**: ~500  
**Linhas de documentação**: ~1,500  
**Status**: ✅ Production Ready

