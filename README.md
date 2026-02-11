# PayFlow Automation API

Sistema automatizado de integração com Conta Azul para processamento e envio de recibos de pagamento via email.

## 🚀 Quick Start

### Setup Local (5 minutos)

```bash
# 1. Clonar e entrar no diretório
cd C:\Projeto\ctrls-payflow-v2\api

# 2. Criar virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate    # Linux/Mac

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Gerar MASTER_KEY
python -c "import base64, secrets; print('MASTER_KEY=' + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

# 5. Configurar .env
cp .env.example .env
# Editar .env com suas credenciais

# 6. Rodar API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 7. Rodar Worker (em outro terminal)
python -m app.worker
```

Acesse: http://localhost:8000/docs

### Setup com Docker

```bash
# Build e iniciar
docker-compose up -d

# Ver logs
docker-compose logs -f api
docker-compose logs -f worker

# Parar
docker-compose down
```

## 📋 Características

- ✅ **OAuth2 Authorization Code Flow** com Conta Azul
- ✅ **Polling periódico** de contas a receber
- ✅ **Criptografia de tokens** em repouso (Fernet AES-128)
- ✅ **Envio automático** de recibos por email (SMTP)
- ✅ **Idempotência forte** (sem reenvios duplicados)
- ✅ **Rate limiting** com backoff exponencial (429)
- ✅ **Proteção SSRF** em downloads de anexos
- ✅ **Logging seguro** (redação de dados sensíveis)
- ✅ **Docker multi-stage** com usuário não-root
- ✅ **Cloudflare Tunnel** + Access (SSO)
- ✅ **Testes completos** (pytest + coverage)

## ⚙️ Configuração

### Variáveis de Ambiente (.env)

```env
# === Conta Azul ===
CONTA_AZUL_CLIENT_ID=seu_client_id
CONTA_AZUL_CLIENT_SECRET=seu_client_secret
CONTA_AZUL_REDIRECT_URI=http://localhost:8000/oauth/callback
# API v2 (não alterar a menos que a Conta Azul mude)
CONTA_AZUL_API_BASE_URL=https://api-v2.contaazul.com
CONTA_AZUL_AUTH_BASE_URL=https://auth.contaazul.com

# === Segurança ===
MASTER_KEY=base64_encoded_32_bytes  # Gerar com comando acima
JWT_SECRET=seu_jwt_secret_aleatorio

# === SMTP (Email) ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_app_password  # Gmail: myaccount.google.com/apppasswords
SMTP_FROM=seu_email@gmail.com
SMTP_REPLY_TO=seu_email@gmail.com
SMTP_USE_TLS=true
SMTP_TIMEOUT=10

# === Database ===
DATABASE_URL=sqlite:///./data/payflow.db

# === Polling ===
POLLING_INTERVAL_SECONDS=300  # 5 minutos
POLLING_SAFETY_WINDOW_MINUTES=10

# === Cloudflare Tunnel (Produção) ===
CLOUDFLARE_TUNNEL_TOKEN=<gerado_na_cloudflare>

# === Fallback de Emails (Opcional) ===
DOCTORS_FALLBACK_JSON={"João Silva": "joao@doctors.com"}
```

### Conta Azul - Criar Aplicação OAuth

1. Acessar [portal.contaazul.com](https://portal.contaazul.com)
2. Menu: **Configurações → Integrações → APIs**
3. **Criar Nova Integração**:
   - Nome: PayFlow Automation
   - Redirect URI: `https://seu-dominio.com/oauth/callback`
   - Escopos: `accounts.read`, `installments.read`, `receipts.read`
4. Copiar **Client ID** e **Client Secret** para `.env`

### SMTP - Exemplos de Configuração

**Gmail** (recomendado para teste):
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=app_password  # Gerar em myaccount.google.com/apppasswords
SMTP_USE_TLS=true
```

**SendGrid**:
```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.sua_api_key
SMTP_USE_TLS=true
```

**Outlook/Office365**:
```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=seu_email@dominio.com
SMTP_PASSWORD=sua_senha
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

**Servidores SSL (porta 465):**
```env
SMTP_PORT=465
SMTP_USE_TLS=false
SMTP_USE_SSL=true  # SSL direto
```

## 🔌 Endpoints Principais

### Health Checks
- `GET /healthz` - Status da API
- `GET /ready` - Readiness probe

### OAuth2
- `GET /connect` - Iniciar autorização Conta Azul
- `GET /oauth/callback` - Callback OAuth2

### Documentação
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    Cloudflare Tunnel + Access                │
│                   (HTTPS + Google SSO)                       │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   FastAPI App   │
                    │   (port 8000)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐    ┌───▼────┐    ┌───▼────┐
         │ OAuth2  │    │ Health │    │  Docs  │
         │ Routes  │    │ Checks │    │ /docs  │
         └────┬────┘    └────────┘    └────────┘
              │
              ▼
    ┌──────────────────┐
    │ ContaAzulAuth    │
    │ Service          │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐       ┌──────────────────┐
    │   SQLite DB      │       │  Crypto Manager  │
    │  (tokens + logs) │       │  (Fernet AES)    │
    └──────────────────┘       └──────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Worker (Polling)                          │
│                    python -m app.worker                      │
└────────────────────────────┬────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐    ┌───▼────┐    ┌───▼────┐
         │ Conta   │    │ Receipt│    │ Mailer │
         │ Azul    │    │ Down-  │    │ Service│
         │ Client  │    │ loader │    │ (SMTP) │
         └─────────┘    └────────┘    └────────┘
```

## 📁 Estrutura do Projeto

```
api/
├── app/
│   ├── main.py                   # FastAPI app
│   ├── config.py                 # Pydantic settings
│   ├── crypto.py                 # Criptografia (Fernet)
│   ├── database.py               # SQLAlchemy models
│   ├── logging.py                # Logging com redação
│   ├── routes_health.py          # Health checks
│   ├── routes_oauth_new.py       # OAuth2 routes
│   ├── services_auth.py          # ContaAzulAuthService
│   ├── services/
│   │   └── mailer.py            # SMTP service
│   └── worker/
│       ├── main.py              # Worker polling loop
│       ├── processor.py         # Financial processor
│       ├── conta_azul_financial_client.py
│       └── receipt_downloader.py
├── tests/
│   ├── test_oauth.py            # OAuth2 tests
│   ├── test_crypto.py           # Encryption tests
│   ├── test_mailer.py           # Email tests
│   ├── test_worker.py           # Worker tests
│   └── test_security_ssrf.py    # SSRF tests
├── migrations/
│   └── versions/
│       └── 001_initial.py       # Alembic migration
├── scripts/
│   ├── generate_key.py          # Gerar MASTER_KEY
│   └── test_oauth.py            # Teste interativo
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## 🧪 Testes

```bash
# Todos os testes
pytest tests/ -v

# Com coverage
pytest tests/ --cov=app --cov-report=html

# Testes específicos
pytest tests/test_oauth.py -v       # OAuth2
pytest tests/test_crypto.py -v      # Criptografia
pytest tests/test_mailer.py -v      # Email
pytest tests/test_worker.py -v      # Worker
pytest tests/test_security_ssrf.py -v  # SSRF
```

### 🔐 OAuth Smoke Test

Para testar se um access_token da Conta Azul está funcionando:

```bash
# Com token na linha de comando
python scripts/contaazul_smoke_test.py <access_token>

# Ou via variável de ambiente
export CONTA_AZUL_ACCESS_TOKEN=<token>
python scripts/contaazul_smoke_test.py
```

O script faz uma chamada real à API v2 da Conta Azul:
- **Endpoint**: `https://api-v2.contaazul.com/v1/pessoas?pagina=1&tamanho_pagina=1`
- **Retorno esperado**: HTTP 200 (token válido)
- **Retorno 401**: Token inválido ou expirado
- **Retorno 404**: Endpoint não existe (verificar URL base)

Este smoke test é executado automaticamente durante o fluxo OAuth no callback.

## 📚 Documentação Adicional

- **[DEPLOY.md](DEPLOY.md)** - Deploy com Docker + Cloudflare Tunnel + Access
- **[SECURITY.md](SECURITY.md)** - Segurança, rotação de chaves, logs
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Solução de problemas comuns

## 🔒 Segurança

### Proteção de Dados Sensíveis
- ✅ Tokens OAuth2 criptografados em repouso (Fernet AES-128)
- ✅ MASTER_KEY via variável de ambiente (32 bytes)
- ✅ Logs redigem tokens, codes, authorization headers
- ✅ SMTP password não é loggado

### Proteção SSRF
- ✅ Validação de URLs de recibos (apenas domínios Conta Azul)
- ✅ Bloqueio de IPs privados e loopback
- ✅ Apenas HTTPS para downloads
- ✅ Sem redirect following

### Rate Limiting
- ✅ Backoff exponencial (429 Too Many Requests)
- ✅ Retry com tenacity (3x com delay)
- ✅ Circuit breaker pattern

### Docker Security
- ✅ Imagem multi-stage (menor superfície de ataque)
- ✅ Usuário não-root (appuser uid=1000)
- ✅ Sem secrets no Dockerfile
- ✅ Healthcheck integrado

## 📊 Monitoramento

### Logs

```bash
# Docker
docker-compose logs -f api
docker-compose logs -f worker

# Local
tail -f logs/payflow.log  # se configurado
```

### Métricas (Sugestões)

Para produção, considere adicionar:
- Prometheus + Grafana (métricas)
- Sentry (error tracking)
- Datadog/New Relic (APM)

## 🤝 Contribuindo

1. Fork o repositório
2. Criar branch: `git checkout -b feature/nova-feature`
3. Commitar: `git commit -am 'Add nova feature'`
4. Push: `git push origin feature/nova-feature`
5. Abrir Pull Request

## 📝 Licença

Proprietário - Uso interno apenas

## 🆘 Suporte

Para problemas ou dúvidas:
1. Verificar [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Abrir issue no GitHub
3. Contatar equipe de desenvolvimento

---

**Versão**: 1.0.0  
**Última atualização**: 2026-02-10

