# Quick Start - PayFlow API

## ⚡ Setup em 5 Minutos

### 1. Gerar MASTER_KEY

```bash
cd C:\Projeto\ctrls-payflow-v2\api
python -c "import base64, secrets; print('MASTER_KEY=' + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

**Saída esperada:**
```
MASTER_KEY=AbCdEfGhIjKlMnOpQrStUvWxYzAb...
```

Copie e guarde em local seguro!

### 2. Criar .env

```bash
cp .env.example .env
```

Editar `C:\Projeto\ctrls-payflow-v2\api\.env`:

```env
# Copie os valores abaixo e preencha com dados reais:

# ===== CONTA AZUL =====
CONTA_AZUL_CLIENT_ID=seu_client_id_aqui
CONTA_AZUL_CLIENT_SECRET=seu_client_secret_aqui
CONTA_AZUL_REDIRECT_URI=http://localhost:8000/oauth/callback

# ===== SEGURANÇA =====
MASTER_KEY=paste_sua_chave_aqui
JWT_SECRET=seu_jwt_secret_aleatorio

# ===== SMTP =====
# Exemplo Gmail:
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_app_password
SMTP_FROM=seu_email@gmail.com
SMTP_REPLY_TO=seu_email@gmail.com
SMTP_USE_TLS=true

# ===== DATABASE =====
DATABASE_URL=sqlite:///./data/payflow.db

# ===== POLLING =====
POLLING_INTERVAL_SECONDS=300
```

### 3. Instalar Dependências

```bash
# Criar venv
python -m venv .venv

# Ativar (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Instalar
pip install -r requirements.txt
```

### 4. Rodar API

```bash
# Terminal 1: API Server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Saída esperada:
# INFO:     Application startup complete
# INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Acesse: http://localhost:8000/docs

### 5. Rodar Worker (em outro terminal)

```bash
# Terminal 2: Worker
.\.venv\Scripts\Activate.ps1
python -m app.worker

# Saída esperada:
# Worker iniciado
# Intervalo de polling: 300s
```

### 6. Testar Fluxo OAuth

```bash
# Terminal 3: Teste
.\.venv\Scripts\Activate.ps1
python scripts/test_oauth.py

# Siga as instruções interativas
```

## 🧪 Rodar Testes

```bash
# Todos os testes
pytest tests/ -v

# Com coverage
pytest tests/ --cov=app --cov-report=html

# Teste específico
pytest tests/test_crypto.py::test_encrypt_decrypt -v
```

## 🐳 Rodar com Docker

```bash
# Build
docker-compose build

# Iniciar
docker-compose up -d

# Ver logs
docker-compose logs -f api
docker-compose logs -f worker

# Parar
docker-compose down
```

## 📋 Checklist de Configuração

### Conta Azul

- [ ] Acessar [portal.contaazul.com](https://portal.contaazul.com)
- [ ] Menu: Configurações → Integrações → APIs
- [ ] Criar Nova Integração
- [ ] Copiar Client ID e Secret para `.env`
- [ ] Definir Redirect URI: `http://localhost:8000/oauth/callback`
- [ ] Ativar escopos: `accounts.read`, `installments.read`, `receipts.read`

### SMTP (Email)

**Gmail:**
- [ ] Ativar 2FA em myaccount.google.com
- [ ] Gerar App Password: myaccount.google.com/apppasswords
- [ ] Copiar para `SMTP_PASSWORD` (não use senha comum!)

**Outlook/Office365:**
- [ ] Host: `smtp.office365.com`
- [ ] Port: `587`
- [ ] User: seu_email@seudominio.com
- [ ] Password: sua_senha

**SendGrid:**
- [ ] Host: `smtp.sendgrid.net`
- [ ] User: `apikey`
- [ ] Password: `SG.sua_api_key`

### Cloudflare Tunnel (Produção)

```bash
# Instalar cloudflared
# https://developers.cloudflare.com/cloudflare-one/connections/connect-applications/install-and-setup/installation/

# Login
cloudflared tunnel login

# Criar túnel
cloudflared tunnel create payflow-api

# Obter token
cloudflared tunnel token payflow-api

# Copiar para .env
CLOUDFLARE_TUNNEL_TOKEN=seu_token_aqui
```

## 🚨 Troubleshooting

### "ModuleNotFoundError: No module named 'app'"

```bash
# Certifique-se de que está na pasta raiz:
cd C:\Projeto\ctrls-payflow-v2\api

# E que venv está ativado:
.\.venv\Scripts\Activate.ps1
```

### "MASTER_KEY deve ser 32 bytes"

```bash
# Regenerar com o script:
python scripts/generate_key.py

# Copiar saída para .env
```

### "SMTP authentication failed"

- Verificar credenciais SMTP em `.env`
- Se Gmail: usar App Password, não senha comum
- Verificar que TLS está habilitado (`SMTP_USE_TLS=true`)

### "Connection refused" para banco de dados

```bash
# Criar pasta data
mkdir data

# Banco será criado automaticamente ao iniciar
```

### Testes falhando com "ImportError"

```bash
# Reinstalar dependências
pip install -r requirements.txt

# Ou com deps de dev
pip install -e ".[dev]"
```

## 📚 Documentação Completa

- **README.md**: Guia completo com todos os detalhes
- **ARCHITECTURE.md**: Visão técnica profunda
- **PAYLOADS.md**: Exemplos de JSONs
- **FILES_INVENTORY.md**: Inventário de todos os arquivos

## 🎯 Próximos Passos

1. ✅ Setup local completo
2. ✅ Testes passando
3. ✅ OAuth funcionando (testar em `/oauth/authorize`)
4. ✅ Email sendo enviado (criar conta de teste)
5. ✅ Deploy via Docker Compose
6. ✅ Configurar Cloudflare Tunnel (produção)

## 💡 Dicas

- Use `make` para comandos comuns:
  ```bash
  make help          # Ver todos os comandos
  make install       # Setup
  make dev           # Rodar API
  make worker        # Rodar worker
  make test          # Rodar testes
  make lint          # Checar código
  make format        # Formatar código
  ```

- Monitorar logs em produção:
  ```bash
  docker-compose logs -f api
  docker-compose logs -f worker
  ```

- Acessar banco de dados:
  ```bash
  sqlite3 data/payflow.db
  SELECT COUNT(*) FROM sent_receipts;
  ```

---

**Tempo estimado**: 5-10 minutos ⏱️  
**Requisitos**: Python 3.10+, pip, git  
**Status**: ✅ Ready to use!

