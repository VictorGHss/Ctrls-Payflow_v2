# PayFlow Automation API

Serviço automatizado para integração com Conta Azul, processamento de recibos de pagamento e envio via email para médicos.

## Características

- ✅ Integração com API Conta Azul (OAuth2)
- ✅ Polling periódico de recibos
- ✅ Envio automático de recibos por email (com PDF anexado)
- ✅ Criptografia de tokens em repouso
- ✅ Idempotência (sem reenvios duplicados)
- ✅ Rate limiting com backoff exponencial (429)
- ✅ Suporte a fallback de emails (mapping local)
- ✅ Logging seguro (redação de dados sensíveis)
- ✅ Docker multi-stage com usuário não-root
- ✅ Cloudflare Tunnel integrado
- ✅ Testes com pytest

## Pré-requisitos

- Python 3.10+
- Docker & Docker Compose (para rodar em container)
- SQLite 3
- Conta Conta Azul com API habilitada
- Servidor SMTP (ex: Gmail, SendGrid, etc)
- (Opcional) Cloudflare Tunnel para exposição remota

## Setup Local (PyCharm + Venv)

### 1. Criar e ativar virtual environment

```bash
cd C:\Projeto\ctrls-payflow-v2\api
python -m venv .venv
.\.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Gerar MASTER_KEY

```bash
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Copiar a saída e adicionar ao `.env`:

```bash
cp .env.example .env
# Editar .env com os valores reais
```

### 4. Configurar .env

```env
# Conta Azul
CONTA_AZUL_CLIENT_ID=seu_client_id
CONTA_AZUL_CLIENT_SECRET=seu_client_secret
CONTA_AZUL_REDIRECT_URI=http://localhost:8000/oauth/callback

# Segurança
MASTER_KEY=<sua_chave_gerada_acima>
JWT_SECRET=seu_jwt_secret

# SMTP
SMTP_HOST=smtp.seuhost.com
SMTP_PORT=587
SMTP_USER=seu_email@dominio.com
SMTP_PASSWORD=sua_senha
SMTP_FROM=seu_email@dominio.com
SMTP_REPLY_TO=seu_email@dominio.com
SMTP_USE_TLS=true

# Database
DATABASE_URL=sqlite:///./data/payflow.db

# Polling
POLLING_INTERVAL_SECONDS=300
```

### 5. Iniciar API (no PyCharm)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Acesse: http://localhost:8000/docs (Swagger)

### 6. Iniciar Worker (em outro terminal)

```bash
python -m app.worker
```

### 7. Rodar testes

```bash
pytest tests/ -v
# Com coverage:
pytest tests/ -v --cov=app --cov-report=html
```

## Docker Compose

### Build e deploy

```bash
# Build das imagens
docker-compose build

# Rodar serviços
docker-compose up -d

# Ver logs
docker-compose logs -f api
docker-compose logs -f worker

# Parar
docker-compose down
```

As imagens usam Python 3.10 slim e rodam com usuário não-root (appuser).

## Integração Conta Azul

### 1. Criar App no Portal Conta Azul

1. Acessar [portal.contaazul.com](https://portal.contaazul.com)
2. Menu: **Configurações → Integrações → APIs**
3. Clicar em **Criar Nova Integração**
4. Preencher:
   - **Nome**: PayFlow Automation
   - **Descrição**: Automação de envio de recibos
   - **Redirect URI**: `https://seu-dominio.com/api/oauth/callback`
   - **Escopos**: `accounts.read`, `installments.read`, `receipts.read`
5. Copiar **Client ID** e **Client Secret** → adicionar ao `.env`

### 2. Configurar Redirect URI

Após expor a API via Cloudflare Tunnel, atualizar:

```env
CONTA_AZUL_REDIRECT_URI=https://seu-dominio-cloudflare.com/api/oauth/callback
```

### 3. Testar Fluxo OAuth

```bash
# 1. Iniciar autorização
GET /oauth/authorize

# 2. Browser será redirecionado para login Conta Azul
# 3. Usuário autoriza
# 4. Callback recebe o código e troca por tokens (salvos criptografados)
```

## Cloudflare Tunnel

### Setup Cloudflare Tunnel + Access

#### 1. Gerar Token de Tunnel

```bash
# Terminal local (com cloudflared instalado)
cloudflared tunnel login

# Criar tunnel
cloudflared tunnel create payflow-api

# Obter token
cloudflared tunnel token payflow-api
```

Copiar token para `.env`:
```env
CLOUDFLARE_TUNNEL_TOKEN=seu_token_aqui
```

#### 2. Configurar DNS no Cloudflare

1. Acessar Cloudflare Dashboard
2. Selecionar domínio
3. **DNS → Records**
4. Adicionar CNAME:
   - **Name**: `payflow` (ou seu prefixo)
   - **Target**: `seu_tunnel_id.cfargotunnel.com`
   - **Proxy status**: Proxied

#### 3. (Opcional) Proteger com Cloudflare Access

1. **Zero Trust → Access → Applications**
2. **Create Application**
3. Preencher:
   - **Application name**: PayFlow API
   - **Session duration**: 24h
   - **Application domain**: `payflow.seu-dominio.com`
4. **Authentication**: Adicionar provedor (Google, GitHub, etc)
5. **Policy**: Definir emails/grupos autorizados

#### 4. Validar Tunnel

```bash
# Verificar se está rodando
curl https://payflow.seu-dominio.com/healthz

# Deve retornar: {"status": "ok"}
```

**Nota**: No docker-compose, o cloudflared usa a variável `CLOUDFLARE_TUNNEL_TOKEN` e `--no-autoupdate` por razões de segurança.

## SMTP (Email)

### Exemplos de Configuração

#### Gmail

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=sua_email@gmail.com
SMTP_PASSWORD=seu_app_password  # Usar App Password, não senha normal
SMTP_FROM=sua_email@gmail.com
SMTP_USE_TLS=true
```

[Gerar App Password do Gmail](https://myaccount.google.com/apppasswords)

#### SendGrid

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.sua_api_key_aqui
SMTP_FROM=seu_email_verificado@dominio.com
SMTP_USE_TLS=true
```

#### Outlook/Office 365

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=sua_email@seudominio.com
SMTP_PASSWORD=sua_senha
SMTP_FROM=sua_email@seudominio.com
SMTP_USE_TLS=true
```

## Fallback de Emails (Mapping de Médicos)

Se a Conta Azul não retornar o email do médico, o sistema busca em um fallback local:

```env
DOCTORS_FALLBACK_JSON={"João Silva": "joao@doctors.com", "Maria Santos": "maria@doctors.com"}
```

Ou criar arquivo `doctors.json`:

```json
{
  "João Silva": "joao@doctors.com",
  "Maria Santos": "maria@doctors.com",
  "Pedro Costa": "pedro@doctors.com"
}
```

Converter para Base64 e adicionar ao `.env`:

```bash
cat doctors.json | base64 -w 0
```

## Estrutura do Projeto

```
api/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app
│   ├── config.py                  # Pydantic settings
│   ├── crypto.py                  # Criptografia (Fernet)
│   ├── logging.py                 # Logging com redação
│   ├── database.py                # SQLAlchemy models
│   ├── conta_azul_client.py        # HTTP client com retry
│   ├── email_service.py            # SMTP email
│   ├── payment_processor.py        # Lógica de negócio
│   ├── routes_health.py            # /healthz, /ready
│   ├── routes_oauth.py             # OAuth flow
│   └── worker.py                  # Polling worker
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Fixtures pytest
│   ├── test_crypto.py             # Testes de criptografia
│   ├── test_idempotency.py        # Testes de idempotência
│   └── test_email.py              # Testes de email
├── .env.example                    # Exemplo de variáveis
├── .gitignore
├── requirements.txt
├── pyproject.toml                  # Black, Ruff, Pytest config
├── Dockerfile                      # Multi-stage
├── docker-compose.yml
└── README.md
```

## Banco de Dados (SQLite)

### Tabelas

1. **oauth_tokens** - Tokens de acesso (criptografados)
2. **azul_accounts** - Contas conectadas
3. **polling_checkpoints** - Último processado (resilência)
4. **sent_receipts** - Recibos enviados (idempotência)
5. **email_logs** - Log de envios

### Migrações (Alembic - Futuro)

Para implementar migrações automáticas:

```bash
pip install alembic
alembic init migrations
```

Por enquanto, as tabelas são criadas automaticamente via SQLAlchemy.

## API Endpoints

### Health

```
GET /healthz
GET /ready
GET /
```

### OAuth

```
GET /oauth/authorize
  Retorna URL de autorização para redirecionar usuário

GET /oauth/callback?code=XXX&state=YYY
  Callback pós-login, troca código por tokens
```

## Segurança

### ✅ Implementado

- **Criptografia em repouso**: MASTER_KEY (Fernet/AES-128)
- **Redação de logs**: Tokens/senhas nunca aparecem
- **Rate limit**: Backoff exponencial em 429
- **HTTPS obrigatório**: Via Cloudflare Tunnel
- **Usuário não-root**: Docker usa appuser
- **SMTP TLS**: Email obrigatoriamente encriptado
- **Idempotência**: Chave única (account_id, installment_id, receipt_id)

### 🔒 Best Practices

1. **MASTER_KEY**: Gerar com `secrets.token_bytes(32)`, guardar em secret management (não git)
2. **JWT_SECRET**: Chave forte e aleatória
3. **SMTP_PASSWORD**: Usar App Passwords, nunca senha primária
4. **Tokens Conta Azul**: Nunca imprimir ou logar
5. **Variáveis sensíveis**: Sempre em `.env`, nunca em código

## Testes

### Rodar todos os testes

```bash
pytest tests/ -v
```

### Rodar teste específico

```bash
pytest tests/test_crypto.py::test_encrypt_decrypt -v
```

### Com coverage

```bash
pytest tests/ --cov=app --cov-report=html
# Abrir htmlcov/index.html
```

### Testes disponíveis

- ✅ **test_crypto.py**: Criptografia/decriptografia
- ✅ **test_idempotency.py**: Idempotência, checkpoints
- ✅ **test_email.py**: Email mockado, parsing de payload

## Qualidade de Código

### Formatação (Black)

```bash
black app/ tests/
```

### Linting (Ruff)

```bash
ruff check app/ tests/
ruff fix app/ tests/  # Auto-fix
```

### Type checking (MyPy)

```bash
mypy app/
```

### Pré-commit (Opcional)

Criar `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.11
    hooks:
      - id: ruff
        args: [--fix]
```

```bash
pip install pre-commit
pre-commit install
```

## Troubleshooting

### Erro: `MASTER_KEY deve ser 32 bytes`

A chave deve ser gerada com:

```bash
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

### Erro: `Connection refused` ao enviar email

Verificar:
- SMTP_HOST e SMTP_PORT corretos
- Credenciais SMTP válidas
- TLS ativo (`SMTP_USE_TLS=true`)
- Firewall não está bloqueando porta 587

### Erro: `Token não encontrado`

Verificar:
- OAuth callback foi executado com sucesso
- Banco de dados está criado (`data/payflow.db`)
- Tabela `oauth_tokens` tem registro

### Worker não está processando

Verificar logs:
```bash
docker-compose logs -f worker
```

Validar:
- `POLLING_INTERVAL_SECONDS` > 0
- Contas ativas no banco (`AzulAccount.is_active = 1`)
- Tokens válidos e não expirados

## Roadmap

- [ ] Alembic para migrações
- [ ] Webhook handler (quando Conta Azul suportar)
- [ ] Dashboard simples (FastAPI + HTML/JS)
- [ ] Rate limit store (Redis)
- [ ] Métricas Prometheus
- [ ] OpenAPI schema documentado

## Licença

MIT

## Contato

Para dúvidas sobre a integração Conta Azul, consultar:
- [Documentação Conta Azul](https://docs.contaazul.com)
- [API Reference](https://api.contaazul.com/docs)

---

**Versão**: 1.0.0  
**Atualizado**: 2025-02-10  
**Status**: Production Ready ✅

