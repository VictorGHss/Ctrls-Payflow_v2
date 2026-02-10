# OAuth2 Authorization Code - Conta Azul

Implementação completa do fluxo OAuth2 Authorization Code para integração com Conta Azul.

## 📋 Endpoints

### GET /connect
Inicia o fluxo OAuth2. Redireciona o usuário para o login/consent da Conta Azul.

```bash
curl http://localhost:8000/connect
# Retorna: Redireciona para https://accounts.contaazul.com/oauth/authorize?...
```

### GET /oauth/callback
Callback que recebe o `authorization code` e troca por `access_token` + `refresh_token`.

Parâmetros:
- `code` (obrigatório): Authorization code da Conta Azul
- `state` (opcional): State para validação CSRF
- `error` (opcional): Código de erro se ocorreu
- `error_description` (opcional): Descrição do erro

Exemplo de resposta bem-sucedida:
```json
{
  "status": "success",
  "message": "Conta Test Company conectada com sucesso!",
  "account_id": "account_123...",
  "owner_name": "Test Owner",
  "owner_email": "owner@example.com",
  "expires_in": 3600
}
```

## 🔐 Segurança Implementada

### ✅ Criptografia em Repouso
- Tokens criptografados com Fernet (AES-128 + HMAC-SHA256)
- MASTER_KEY (32 bytes) vindo de variável de ambiente
- Tokens não são acessíveis em plaintext no banco de dados

### ✅ Redação em Logs
- Authorization headers redados automaticamente
- Tokens não aparecem em logs
- Códigos de autorização não aparecem em logs

### ✅ Refresh Token Rotation
- Refresh token muda a cada renovação (como exigido por OAuth2 spec)
- Novo refresh token é sempre salvo no banco
- Access token é renovado automaticamente quando expirado

### ✅ Validação de Estado (CSRF)
- State aleatório gerado para cada fluxo
- Pode ser validado em callback (implementação futura)

## 🗂️ Arquitetura

```
routes_oauth_new.py          (Endpoints HTTP)
    ↓
services_auth.py             (Lógica de autenticação)
    ↓
    ├─ exchange_code_for_tokens()  (Troca code → tokens)
    ├─ get_account_info()          (Busca dados da conta)
    ├─ save_tokens()               (Salva criptografado)
    ├─ refresh_access_token()      (Renova token expirado)
    └─ is_token_expired()          (Verifica expiração)
    ↓
crypto.py                    (Criptografia Fernet)
    ↓
database.py                  (Models SQLAlchemy)
    ├─ OAuthToken
    └─ AzulAccount
```

## 📊 Models Criados

### OAuthToken
```python
class OAuthToken(Base):
    account_id: str          # ID da conta (unique)
    access_token: str        # Criptografado
    refresh_token: str       # Criptografado
    expires_at: datetime     # Quando access_token expira
    created_at: datetime
    updated_at: datetime
```

### AzulAccount
```python
class AzulAccount(Base):
    account_id: str          # ID da conta (unique)
    owner_name: str
    owner_email: str
    company_name: str
    is_active: int           # 1 ou 0
    connected_at: datetime
    disconnected_at: datetime
    metadata: dict (JSON)
```

## 🔄 Fluxo Completo

```
1. Usuário acessa GET /connect
   ↓
2. API redireciona para Conta Azul (AUTHORIZE_URL)
   ↓
3. Usuário faz login e consente
   ↓
4. Conta Azul redireciona para GET /oauth/callback?code=...
   ↓
5. API troca code por tokens (exchange_code_for_tokens)
   ↓
6. API busca informações da conta (get_account_info)
   ↓
7. API salva tokens criptografados (save_tokens)
   ↓
8. Retorna sucesso ao usuário
```

## 🧪 Testes

### Executar todos os testes OAuth:
```bash
pytest tests/test_oauth.py -v
```

### Testes inclusos:
- ✅ Criptografia Fernet (encrypt/decrypt)
- ✅ Decrypt de dados inválidos (erro)
- ✅ Caracteres especiais
- ✅ Unicode
- ✅ Salvamento de novo token
- ✅ Atualização de token existente
- ✅ Verificação de expiração
- ✅ Criação de AzulAccount
- ✅ Atualização de AzulAccount
- ✅ Tokens criptografados em repouso (at-rest)

### Executar com coverage:
```bash
pytest tests/test_oauth.py -v --cov=app.services_auth --cov-report=html
```

## 🚀 Uso

### 1. Configurar .env
```env
CONTA_AZUL_CLIENT_ID=seu_client_id
CONTA_AZUL_CLIENT_SECRET=seu_client_secret
CONTA_AZUL_REDIRECT_URI=http://localhost:8000/oauth/callback

MASTER_KEY=base64_encoded_32_bytes
JWT_SECRET=seu_secret

# ... outros settings
```

### 2. Rodar a API
```bash
uvicorn app.main:app --reload
```

### 3. Iniciar fluxo OAuth
```bash
# No browser, acesse:
http://localhost:8000/connect

# Ou via curl:
curl -L http://localhost:8000/connect
```

### 4. Após autorizar na Conta Azul
- Será redirecionado para `http://localhost:8000/oauth/callback?code=...`
- Tokens serão salvos automaticamente
- Resposta JSON confirma sucesso

## 📈 Renovação Automática de Token

Quando `access_token` expirar, usar:

```python
from app.services_auth import ContaAzulAuthService
from app.database import SessionLocal

db = SessionLocal()
auth_service = ContaAzulAuthService(db)

# Renovar token (async)
new_access_token = await auth_service.refresh_access_token(
    account_id="account_123"
)
```

**Importante**: Refresh token é salvo automaticamente (muda a cada renovação).

## ⚠️ Regras Obrigatórias Implementadas

- ✅ Access token expira em ~1h
- ✅ Refresh token salvo e renovado
- ✅ Refresh token muda a cada renovação
- ✅ Tokens criptografados em repouso (MASTER_KEY)
- ✅ Logs redigem tokens e códigos
- ✅ State aleatório para CSRF (sem validação, implementação futura)

## 📝 Próximos Passos

- [ ] Implementar validação de state (CSRF protection)
- [ ] Implementar webhook para token revocation
- [ ] Adicionar refresh token no evento de startup
- [ ] Implementar token cleanup (apagar tokens antigos)
- [ ] Adicionar rate limiting em token refresh

## 🔗 Referências

- [OAuth2 Authorization Code Flow](https://tools.ietf.org/html/rfc6749#section-1.3.1)
- [Conta Azul API Docs](https://docs.contaazul.com)
- [Fernet Cryptography](https://cryptography.io/en/latest/fernet/)

