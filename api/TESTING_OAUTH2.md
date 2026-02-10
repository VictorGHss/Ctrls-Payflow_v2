# 🧪 Como Testar OAuth2 Localmente

## Pré-requisitos

```bash
# Ativar venv
.\.venv\Scripts\Activate.ps1

# Instalar dependências (se ainda não fez)
pip install -r requirements.txt
```

## 1. Setup do Ambiente

### Gerar MASTER_KEY
```bash
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

### Configurar .env
```bash
cp .env.example .env
```

Editar `C:\Projeto\ctrls-payflow-v2\api\.env`:
```env
# Obrigatório
CONTA_AZUL_CLIENT_ID=seu_client_id_aqui
CONTA_AZUL_CLIENT_SECRET=seu_client_secret_aqui
CONTA_AZUL_REDIRECT_URI=http://localhost:8000/oauth/callback

MASTER_KEY=<sua_chave_gerada_acima>
JWT_SECRET=seu_jwt_secret_qualquer

# Opcionais para testes
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_app_password
```

## 2. Rodar Testes Unitários

### Testes de Criptografia + Persistência
```bash
pytest tests/test_oauth.py -v
```

Output esperado:
```
tests/test_oauth.py::test_crypto_encrypt_decrypt PASSED
tests/test_oauth.py::test_crypto_encrypt_different_outputs PASSED
tests/test_oauth.py::test_crypto_special_chars PASSED
tests/test_oauth.py::test_crypto_unicode PASSED
tests/test_oauth.py::test_save_tokens_new_account PASSED
tests/test_oauth.py::test_save_tokens_update_existing PASSED
tests/test_oauth.py::test_get_token PASSED
tests/test_oauth.py::test_is_token_expired PASSED
tests/test_oauth.py::test_save_creates_azul_account PASSED
tests/test_oauth.py::test_save_updates_azul_account PASSED
tests/test_oauth.py::test_tokens_encrypted_at_rest PASSED
... (17 testes total)

======================== 17 passed in 0.XX seconds =========================
```

### Com Coverage
```bash
pytest tests/test_oauth.py -v --cov=app.services_auth --cov-report=html
```

## 3. Rodar API Localmente

### Terminal 1: Rodar FastAPI
```bash
uvicorn app.main:app --reload --port 8000
```

Você verá:
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2: Testar endpoints

#### Test 1: Health Check
```bash
curl http://localhost:8000/healthz
```

Resposta:
```json
{"status": "ok"}
```

#### Test 2: Swagger
```
Abra no browser:
http://localhost:8000/docs
```

Você verá a documentação Swagger com:
- ✅ GET /connect
- ✅ GET /oauth/callback
- ✅ GET /healthz
- ✅ GET /ready

#### Test 3: Iniciar fluxo OAuth
```bash
# Opção 1: Browser
http://localhost:8000/connect

# Opção 2: Curl (vai retornar redirect)
curl -L http://localhost:8000/connect
```

Resultado:
- Você será redirecionado para: `https://accounts.contaazul.com/oauth/authorize?...`
- Ou se não tiver credenciais reais, receberá um erro HTTP

## 4. Teste de Integração (com Conta Azul Real)

**IMPORTANTE**: Você precisa ter credenciais reais da Conta Azul.

### Criar Integração OAuth na Conta Azul
1. Acessar: https://portal.contaazul.com
2. Menu: Configurações → Integrações → APIs
3. Criar integração:
   - Client ID: `seu_client_id`
   - Client Secret: `seu_client_secret`
   - Redirect URI: `http://localhost:8000/oauth/callback`
   - Escopos: `accounts.read installments.read receipts.read`

### Testar Fluxo Completo
1. Atualizar .env com credenciais reais
2. Rodar API: `uvicorn app.main:app --reload`
3. No browser: `http://localhost:8000/connect`
4. Fazer login na Conta Azul
5. Autorizar app
6. Será redirecionado para callback
7. Você receberá resposta JSON com sucesso:
   ```json
   {
     "status": "success",
     "message": "Conta ... conectada com sucesso!",
     "account_id": "account_123...",
     "owner_name": "...",
     "owner_email": "..."
   }
   ```
8. Tokens foram salvos criptografados no banco SQLite

## 5. Verificar Dados no Banco

```bash
# Abrir SQLite
sqlite3 data/payflow.db

# Listar tokens (criptografados)
SELECT account_id, access_token, refresh_token, expires_at FROM oauth_tokens;

# Listar contas
SELECT account_id, owner_name, company_name, is_active FROM azul_accounts;

# Sair
.exit
```

Você verá:
- `access_token`: String começando com `gAAAAAA...` (Fernet)
- `refresh_token`: String começando com `gAAAAAA...` (Fernet)
- **Não há plaintext!** (criptografado em repouso)

## 6. Testar Renovação de Token

Script de teste:
```python
# test_refresh_token.py
import asyncio
from app.database import SessionLocal
from app.services_auth import ContaAzulAuthService

async def test_refresh():
    db = SessionLocal()
    auth = ContaAzulAuthService(db)
    
    account_id = "seu_account_id_aqui"
    
    # Renovar token
    new_token = await auth.refresh_access_token(account_id)
    
    if new_token:
        print(f"✅ Token renovado com sucesso!")
        print(f"   Novo access_token: {new_token[:20]}...")
    else:
        print("❌ Falha ao renovar token")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(test_refresh())
```

Executar:
```bash
python test_refresh_token.py
```

## 7. Logs com Redação

Quando estiver processando, você verá logs como:
```
INFO:     Application startup complete
INFO:     PayFlow API iniciada - 1.0.0
INFO:app.routes_oauth_new:Iniciando fluxo OAuth - redirecionando para Conta Azul
INFO:app.services_auth:URL de autorização gerada com state=abc123...
INFO:app.services_auth:Token obtido com sucesso. Expires in: 3600s
INFO:app.services_auth:Informações da conta obtidas: id=account...
INFO:app.services_auth:Novo token criado para conta account...
INFO:app.services_auth:Nova conta registrada: account...
```

**Note**: Tokens, códigos e secrets **NÃO** aparecem nos logs!

## 8. Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'pytest'"
```bash
pip install pytest pytest-cov
```

### Erro: "MASTER_KEY deve ser 32 bytes"
```bash
python scripts/generate_key.py
# Copie para .env
```

### Erro: "Porta 8000 já em uso"
```bash
uvicorn app.main:app --reload --port 8001
```

### Erro: "Connection refused" ao testar OAuth real
- Verificar credenciais do .env
- Verificar se redirect_uri está correto
- Certificar que Conta Azul OAuth está ativa

## ✅ Checklist

- [ ] Rodei pytest e todos os 17 testes passaram
- [ ] Rodei `uvicorn app.main:app --reload`
- [ ] Acessei http://localhost:8000/docs
- [ ] Testei GET /healthz
- [ ] Testei GET /connect (com credenciais reais)
- [ ] Completei fluxo OAuth com Conta Azul
- [ ] Verifiquei tokens no banco (criptografados)
- [ ] Verifiquei logs (sem plaintext secrets)

## 📚 Mais Informações

Veja:
- `OAUTH2_IMPLEMENTACAO.md` - Guia completo
- `README.md` - Documentação geral
- `ARCHITECTURE.md` - Visão técnica

