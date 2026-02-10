# Arquitetura PayFlow API

## Visão Geral

PayFlow é um serviço automatizado que:

1. **Conecta** com Conta Azul via OAuth2
2. **Monitora** recibos/parcelas em polling periódico
3. **Baixa** PDFs dos recibos
4. **Envia** emails para médicos (com PDF anexado)
5. **Rastreia** idempotência (sem reenvios)
6. **Registra** tudo com segurança (redação de logs)

## Componentes Principais

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Web Server                   │
│                                                         │
│  ┌──────────────────┐         ┌──────────────────┐    │
│  │  GET /oauth      │         │ GET /oauth/      │    │
│  │  /authorize      │────────▶│ callback?code=.. │    │
│  └──────────────────┘         └──────────────────┘    │
│           │                            │               │
│           │                            ▼               │
│           │                   ┌─────────────────┐      │
│           │                   │ Conta Azul      │      │
│           └──────────────────▶│ OAuth Endpoint  │      │
│                               └─────────────────┘      │
│                                                         │
│  Endpoints: /healthz, /ready, /docs                    │
└─────────────────────────────────────────────────────────┘
         ▲
         │
         │ HTTP (FastAPI) :8000
         │
    ┌────┴────┐
    │ Internet│
    └────┬────┘
         │
    Cloudflare Tunnel
         │
    HTTPS Public
```

### 1. **API Server (FastAPI)**

**Arquivo**: `app/main.py`

Responsabilidades:
- Servir rotas HTTP (OAuth, health checks)
- Dependency injection para DB
- Middleware de segurança (CORS, trusted hosts)

**Rotas**:
- `GET /` - Info do serviço
- `GET /healthz` - Health check
- `GET /ready` - Readiness check
- `GET /oauth/authorize` - Inicia fluxo OAuth
- `GET /oauth/callback` - Recebe código, troca por token

---

### 2. **Worker (Background Job)**

**Arquivo**: `app/worker.py`

Responsabilidades:
- Loop infinito com polling periódico (ex: a cada 5 min)
- Buscar contas ativas
- Para cada conta, executar `PaymentProcessor`
- Registrar logs de sucesso/erro

```python
Cada ciclo:
  1. Buscar todas as AzulAccount (is_active=1)
  2. Para cada conta:
     a. Buscar último checkpoint (ou usar 30 dias atrás)
     b. Chamar Conta Azul API para parcelas/recibos
     c. Para cada parcela "recebida":
        - Verificar se já foi enviada (idempotência)
        - Baixar PDF do recibo
        - Resolver email do médico
        - Enviar email com PDF
        - Registrar em sent_receipts
     d. Atualizar checkpoint
  3. Aguardar POLLING_INTERVAL_SECONDS
  4. Próximo ciclo
```

---

### 3. **Lógica de Negócio (Payment Processor)**

**Arquivo**: `app/payment_processor.py`

Classes:
- `DoctorFallbackResolver` - Resolve email do médico via mapping
- `PaymentProcessor` - Orquestra todo o fluxo

Fluxo:
```
get_active_accounts()
  ↓
para cada account:
  ├─ get_oauth_token (criptografado)
  ├─ get_polling_checkpoint
  ├─ client.get_installments(filter_date)
  └─ para cada installment "received":
      ├─ is_receipt_already_sent? (idempotência)
      ├─ client.download_attachment (PDF)
      ├─ doctor_resolver.resolve (email)
      ├─ email_service.send_receipt_email
      ├─ SentReceipt.create (register)
      ├─ EmailLog.create (register)
      └─ update_checkpoint
```

---

### 4. **Conta Azul Client (HTTP)**

**Arquivo**: `app/conta_azul_client.py`

Responsabilidades:
- Comunicação HTTP com API Conta Azul
- **Rate limiting**: Detecta 429 e aplica backoff exponencial
- **Retry**: Exponential backoff (1s, 2s, 4s, 8s, 16s)
- **Timeout**: 30 segundos por requisição

Métodos:
- `get(endpoint, params)` - GET genérico
- `post(endpoint, json_data)` - POST genérico
- `get_installments(filter_date)` - Busca parcelas
- `download_attachment(url)` - Baixa PDF

---

### 5. **Email Service**

**Arquivo**: `app/email_service.py`

Responsabilidades:
- Conexão SMTP com TLS obrigatório
- Construção de MIME multipart (texto + PDF)
- Envio com tratamento de erros

Métodos:
- `send_email(to_email, subject, body, pdf_content, ...)` - Genérico
- `send_receipt_email(doctor_email, customer_name, ...)` - Formatado

---

### 6. **Criptografia**

**Arquivo**: `app/crypto.py`

- **Algoritmo**: Fernet (AES-128-CBC + HMAC-SHA256)
- **Chave**: MASTER_KEY (32 bytes em base64)
- **Dados criptografados**: access_token, refresh_token

```python
# No banco de dados:
OAuthToken:
  access_token = ciphertextABC123...  # criptografado
  refresh_token = ciphertextXYZ789...  # criptografado
  expires_at = 2025-02-10 11:30:00

# Na memória (durante processamento):
access_token = "eyJhbGc..."  # plaintext
```

---

### 7. **Logging com Redação**

**Arquivo**: `app/logging.py`

- `SensitiveDataFilter` filtra logs antes de enviar ao console/arquivo
- Regex patterns detectam:
  - `authorization`, `access_token`, `refresh_token` → `***REDACTED***`
  - `password`, `passwd` → `***REDACTED***`
  - `api_key`, `apikey` → `***REDACTED***`

Exemplo:
```
# Sem redação:
Authorization: Bearer eyJhbGc...

# Com redação:
Authorization: ***REDACTED***
```

---

### 8. **Database (SQLAlchemy + SQLite)**

**Arquivo**: `app/database.py`

Tabelas:

```
oauth_tokens
├─ id (PK)
├─ account_id (FK, unique)
├─ access_token (TEXT, criptografado)
├─ refresh_token (TEXT, criptografado)
├─ expires_at (DATETIME)
└─ created_at, updated_at

azul_accounts
├─ id (PK)
├─ account_id (FK, unique)
├─ owner_name, owner_email
├─ company_name
├─ is_active (1/0)
└─ connected_at, disconnected_at

polling_checkpoints
├─ id (PK)
├─ account_id (FK, unique)
├─ last_processed_date (DATETIME)
├─ last_processed_id (VARCHAR)
└─ updated_at

sent_receipts (idempotência)
├─ id (PK)
├─ account_id, installment_id, receipt_id
├─ receipt_url
├─ doctor_email
├─ sent_at
├─ metadata (JSON)
└─ UNIQUE (account_id, installment_id, receipt_id)

email_logs
├─ id (PK)
├─ account_id, receipt_id
├─ doctor_email
├─ status ('sent', 'failed', 'pending')
├─ error_message
└─ created_at, updated_at
```

---

## Fluxo de Dados

### 1. Inicialização (Primeira Vez)

```
Usuário clica "Conectar Conta Azul"
  ↓
GET /oauth/authorize
  → Gera state (CSRF)
  → Retorna URL de autorização da Conta Azul
  ↓
Browser redireciona para Conta Azul (login)
  ↓
Usuário autoriza no portal Conta Azul
  ↓
Conta Azul redireciona para /oauth/callback?code=...
  ↓
Sistema troca código por tokens (access + refresh)
  ↓
Criptografa tokens (Fernet)
  ↓
Salva no banco (OAuthToken, AzulAccount)
  ↓
Retorna sucesso ao usuário
```

### 2. Polling Periódico

```
Worker loop (a cada 5 min)
  ↓
get_active_accounts() → [AzulAccount]
  ↓
Para cada account:
  ├─ get_oauth_token (decrypt)
  ├─ get_polling_checkpoint
  ├─ ContaAzulClient.get_installments(filter_date)
  │   → Conta Azul API (com rate limit handling)
  │   → 10 parcelas recebidas
  │
  ├─ Para cada parcela:
  │   ├─ Checar: is_receipt_already_sent?
  │   │   → YES: Skip
  │   │   → NO: Continua
  │   │
  │   ├─ Resolver email do médico
  │   │   → Extrair da parcela se houver
  │   │   → Fallback via mapping local
  │   │   → NULL: Skip (log warning)
  │   │
  │   ├─ Baixar PDF (via URL no recibo)
  │   ├─ Enviar email com PDF
  │   │   → SMTP TLS
  │   │   → Log de envio
  │   │
  │   ├─ Registrar em sent_receipts (unique constraint)
  │   └─ Log em email_logs
  │
  ├─ Atualizar checkpoint (data/ID da última parcela)
  └─ Próximo account
```

---

## Segurança

### 🔐 Em Repouso (At Rest)

```
SQLite Database: ./data/payflow.db
├─ oauth_tokens.access_token: CRIPTOGRAFADO (Fernet)
├─ oauth_tokens.refresh_token: CRIPTOGRAFADO (Fernet)
└─ Chave: MASTER_KEY (ambiente, nunca em git)
```

### 🔒 Em Trânsito (In Transit)

- **OAuth Conta Azul**: HTTPS obrigatório
- **API Externa (Conta Azul)**: HTTPS + Bearer token
- **Cloudflare Tunnel**: HTTPS end-to-end
- **SMTP**: TLS obrigatório (startTLS na porta 587)

### 🚫 Em Logs (In Logs)

```
# Antes (inseguro):
DEBUG Authorization: Bearer eyJhbGc...

# Depois (seguro com SensitiveDataFilter):
DEBUG Authorization: ***REDACTED***
```

### ✅ Outras Medidas

- **Usuário não-root**: Docker (appuser:1000)
- **CORS restrito**: Apenas Conta Azul pode fazer callback
- **Rate limit**: Backoff exponencial (429)
- **Idempotência**: Chave única (unique constraint)

---

## Ciclo de Vida dos Tokens

### Access Token

```
Gerado em: GET /oauth/callback (exchange code)
Duração: ~1 hora (3600s)
Uso: Cada requisição para Conta Azul
Expiração: Verificado antes de usar
  → Se expirado: renovar via refresh_token
  → Se sucesso: atualizar expires_at
```

### Refresh Token

```
Gerado em: GET /oauth/callback (exchange code)
Muda em: Cada renovação (novo refresh_token retornado)
Salvo: Sempre que renovar
Criptografia: Fernet (MASTER_KEY)
Armazenado: OAuthToken.refresh_token
```

### Renovação Automática

```
Quando necessário:
  1. Detectar access_token expirado
  2. Chamar routes_oauth.refresh_access_token()
  3. POST para Conta Azul /oauth/token
     body: grant_type=refresh_token, refresh_token=...
  4. Receber novo access_token + novo refresh_token
  5. Atualizar DB (ambos)
  6. Continuar requisição original
```

---

## Rate Limiting

### Conta Azul Limits

```
600 requisições / minuto
10 requisições / segundo

Header: X-RateLimit-Remaining
```

### Implementação PayFlow

```
ContaAzulClient._retry_with_backoff()
  1. Fazer requisição
  2. Se 429 (Too Many Requests):
     wait_time = 1 * (2 ^ attempt)
     Retry: 1s, 2s, 4s, 8s, 16s
  3. Se 200: OK, continua
  4. Se outro erro: raise (não retry)
```

---

## Idempotência

### Problema

```
Worker falha após enviar email mas antes de registrar
→ Próximo ciclo reenvia mesmo recibo
→ Médico recebe duplicado
```

### Solução

```
Tabela: sent_receipts
├─ account_id
├─ installment_id
├─ receipt_id
└─ UNIQUE(account_id, installment_id, receipt_id)

Lógica:
  1. Antes de enviar: is_receipt_already_sent()?
  2. Se YES: Skip (log info)
  3. Se NO:
     a. Enviar email
     b. INSERT sent_receipts (unique constraint)
     c. Se INSERT falhar (violação): já foi enviado antes (race condition)
     d. Registrar EmailLog
```

---

## Fallback de Emails

### Cenário 1: Conta Azul retorna email

```
installment.doctorEmail = "joao@doctors.com"
→ Usar diretamente
```

### Cenário 2: Conta Azul não retorna, mas há mapping local

```
DOCTORS_FALLBACK_JSON = '{"João Silva": "joao@doctors.com"}'
installment.customerName = "João Silva"
→ Buscar em mapping
→ joao@doctors.com
```

### Cenário 3: Nenhum email disponível

```
installment.doctorEmail = null
installment.customerName = "Cliente Novo"
DOCTORS_FALLBACK_JSON = {} (sem mapping)
→ Log warning
→ Skip email
→ Marcar com erro em email_logs
```

---

## Deployment

### Local (PyCharm)

```bash
# Terminal 1: API
uvicorn app.main:app --reload

# Terminal 2: Worker
python -m app.worker

# Terminal 3: Tests
pytest tests/ -v
```

### Docker Compose

```bash
docker-compose up -d

# Serviços:
# - api (FastAPI :8000)
# - worker (polling)
# - cloudflared (tunnel)
```

### Produção (Via Cloudflare Tunnel)

```
Internet
  ↓ (HTTPS)
Cloudflare Tunnel
  ↓
Docker container (api:8000)
  ↓
FastAPI / Worker
  ↓
SQLite (./data/payflow.db)
```

---

## Monitoramento

### Health Check

```
GET /healthz → {"status": "ok"}
GET /ready → {"status": "ready"}
```

### Logs

```
# Arquivo: ./logs/app.log (se configurado)
# Console: stdout (Docker)

Formato:
  2025-02-10 10:30:45 | app.payment_processor | INFO | Processando conta: test_account_001
  2025-02-10 10:30:46 | app.email_service | INFO | Email enviado com sucesso para joao@doctors.com
  2025-02-10 10:30:47 | app.conta_azul_client | WARNING | Rate limit atingido. Aguardando 2s
```

### Database

```bash
# Abrir SQLite:
sqlite3 ./data/payflow.db

# Queries úteis:
SELECT COUNT(*) FROM sent_receipts;
SELECT * FROM email_logs ORDER BY created_at DESC LIMIT 10;
SELECT * FROM oauth_tokens;
SELECT * FROM polling_checkpoints;
```

---

## Roadmap / TODO

- [ ] Implementar Alembic para migrações
- [ ] Webhook handler (quando Conta Azul suportar)
- [ ] Dashboard simples (React/Vue frontend)
- [ ] Redis para rate limit store (distribuído)
- [ ] Métricas Prometheus
- [ ] Alertas (ex: email para admin se 10 erros em 1h)
- [ ] Testes de integração com API real Conta Azul
- [ ] CI/CD (GitHub Actions, etc)

---

**Versão**: 1.0.0  
**Data**: 2025-02-10  
**Status**: Production Ready ✅

