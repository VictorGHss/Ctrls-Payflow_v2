# 🔒 Segurança - PayFlow API

Guia de segurança, gestão de secrets e melhores práticas.

## 📋 Visão Geral

O PayFlow implementa múltiplas camadas de segurança:

- ✅ **Criptografia em repouso** (tokens OAuth2)
- ✅ **MASTER_KEY** via variável de ambiente
- ✅ **Logging com redação** de dados sensíveis
- ✅ **Proteção SSRF** em downloads de anexos
- ✅ **Rate limiting** com backoff exponencial
- ✅ **Docker não-root** (uid=1000)
- ✅ **Cloudflare Access** (SSO)
- ✅ **TLS obrigatório** para SMTP

---

## 🔑 Gestão de Secrets

### O que é Segredo?

**Nunca devem estar no código ou logs:**

| Secret | Onde Está | Propósito |
|--------|-----------|-----------|
| MASTER_KEY | `.env` | Criptografia de tokens OAuth2 |
| JWT_SECRET | `.env` | (Reservado para futura autenticação) |
| CONTA_AZUL_CLIENT_SECRET | `.env` | OAuth2 com Conta Azul |
| SMTP_PASSWORD | `.env` | Autenticação SMTP |
| CLOUDFLARE_TUNNEL_TOKEN | `.env` | Conexão com Cloudflare |
| OAuth2 access_token | Memória/DB criptografado | API Conta Azul |
| OAuth2 refresh_token | DB criptografado | Renovação de tokens |

### Como Armazenar Secrets

**❌ NUNCA fazer:**
```python
# ❌ Hardcoded
MASTER_KEY = "abc123..."

# ❌ Commitar .env
git add .env  # ERRADO!

# ❌ Logar secrets
logger.info(f"Token: {access_token}")  # ERRADO!
```

**✅ Fazer:**
```python
# ✅ Via variáveis de ambiente
from app.config import get_settings
settings = get_settings()
master_key = settings.MASTER_KEY

# ✅ .gitignore
.env
.env.local
*.key

# ✅ Logar com redação
logger.info(f"Token: {access_token[:10]}***")  # OK
```

---

## 🔐 MASTER_KEY

### O que é?

A MASTER_KEY é uma chave simétrica de 32 bytes usada para criptografar/descriptografar tokens OAuth2 no banco de dados.

**Algoritmo**: Fernet (AES-128 CBC + HMAC-SHA256)

### Gerar MASTER_KEY

```bash
# Python
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

# OpenSSL
openssl rand -base64 32

# Output esperado:
# AbCdEfGhIjKlMnOpQrStUvWxYz0123456789+/==
```

### Configurar

```env
# .env
MASTER_KEY=AbCdEfGhIjKlMnOpQrStUvWxYz0123456789+/==
```

### Armazenamento em Produção

**Opções recomendadas:**

**1. Docker Secrets** (Docker Swarm):
```yaml
# docker-compose.yml
secrets:
  master_key:
    external: true

services:
  api:
    secrets:
      - master_key
    environment:
      MASTER_KEY_FILE: /run/secrets/master_key
```

**2. Kubernetes Secrets**:
```bash
kubectl create secret generic payflow-secrets \
  --from-literal=MASTER_KEY='AbCdEf...'
```

**3. HashiCorp Vault**:
```bash
# Escrever
vault kv put secret/payflow MASTER_KEY='AbCdEf...'

# Ler
vault kv get -field=MASTER_KEY secret/payflow
```

**4. AWS Secrets Manager**:
```python
import boto3
client = boto3.client('secretsmanager')
response = client.get_secret_value(SecretId='payflow/master-key')
master_key = response['SecretString']
```

---

## 🔄 Rotação de MASTER_KEY

### Quando Rotacionar?

- **Anualmente** (best practice)
- **Após suspeita de comprometimento**
- **Mudança de pessoal** (funcionários com acesso)
- **Auditoria de segurança**

### Procedimento (Zero Downtime)

#### 1. Gerar Nova Chave

```bash
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Salvar como: `NEW_MASTER_KEY`

#### 2. Backup do Banco

```bash
cp data/payflow.db data/payflow.db.backup.$(date +%Y%m%d_%H%M%S)
```

#### 3. Adicionar Chave Antiga ao .env

```env
# .env

# Chaves antigas (para backward compatibility)
OLD_MASTER_KEYS=<CHAVE_ANTIGA>

# Nova chave (será usada para novos encrypts)
MASTER_KEY=<NEW_MASTER_KEY>
```

#### 4. Rebuild e Reiniciar

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### 5. Verificar Logs

```bash
docker-compose logs api | grep -i "crypto\|initialized"

# Esperado:
# INFO: Crypto inicializado com chave v2
```

#### 6. Re-criptografar Tokens (Opcional)

Para não manter `OLD_MASTER_KEYS` indefinidamente:

```bash
docker-compose exec api bash

python3 << 'EOF'
from app.crypto import get_crypto_manager
from app.database import init_db, OAuthToken
from app.config import get_settings

settings = get_settings()
engine, SessionLocal = init_db(settings.DATABASE_URL)
db = SessionLocal()
crypto = get_crypto_manager()

# Para cada token
tokens = db.query(OAuthToken).all()
for token in tokens:
    try:
        # Descriptografar com chave antiga
        plaintext_access = crypto.decrypt(token.access_token)
        plaintext_refresh = crypto.decrypt(token.refresh_token)
        
        # Re-criptografar com nova chave
        token.access_token = crypto.encrypt(plaintext_access)
        token.refresh_token = crypto.encrypt(plaintext_refresh)
        
        print(f"✅ Re-criptografado: {token.account_id[:10]}...")
    except Exception as e:
        print(f"❌ Erro: {token.account_id[:10]}... - {e}")

db.commit()
print(f"✅ Total: {len(tokens)} tokens re-criptografados")
EOF

exit
```

#### 7. Remover OLD_MASTER_KEYS (Após 24h)

```bash
nano .env
# Remover linha: OLD_MASTER_KEYS=...

docker-compose restart
```

---

## 📝 Logging Seguro

### Redação Automática

O sistema redige automaticamente:

**Headers HTTP:**
```python
# app/logging.py
class SensitiveDataFilter:
    def filter(self, record):
        # Redige Authorization headers
        record.msg = re.sub(
            r'Authorization:\s*Bearer\s+[\w\-\.]+',
            'Authorization: Bearer ***REDACTED***',
            record.msg
        )
        return True
```

**Tokens OAuth2:**
```python
# Antes
logger.info(f"Token obtido: {access_token}")

# Depois (automático)
logger.info(f"Token obtido: eyJhbGci***REDACTED***")
```

**OAuth Codes:**
```python
# Antes
logger.info(f"Code recebido: {code}")

# Depois (automático)
logger.info(f"Code recebido: abc123***REDACTED***")
```

### Níveis de Log

**Produção** (`.env`):
```env
LOG_LEVEL=INFO
```

**Desenvolvimento** (`.env`):
```env
LOG_LEVEL=DEBUG
```

**Níveis disponíveis:**
- `DEBUG` - Todas as mensagens (incluindo internals)
- `INFO` - Informações gerais (recomendado produção)
- `WARNING` - Avisos
- `ERROR` - Erros
- `CRITICAL` - Erros críticos

### Verificar Logs

```bash
# Produção: apenas INFO+
docker-compose logs api | grep -E "INFO|WARNING|ERROR"

# Ver erros apenas
docker-compose logs api | grep ERROR

# Ver últimas 100 linhas
docker-compose logs --tail=100 api
```

---

## 🛡️ Proteção SSRF (Server-Side Request Forgery)

### O que é SSRF?

Ataque onde um atacante manipula a aplicação para fazer requests HTTP para destinos não autorizados (ex: AWS metadata, rede interna).

### Implementação no PayFlow

**Validação de URLs** em `app/worker/conta_azul_financial_client.py`:

```python
def _validate_receipt_url(self, url: str) -> bool:
    """Valida URL de recibo (SSRF prevention)."""
    parsed = urlparse(url)
    
    # 1. Apenas HTTPS
    if parsed.scheme != "https":
        logger.warning(f"URL não-HTTPS rejeitada: {url}")
        return False
    
    # 2. Apenas domínios Conta Azul
    allowed_domains = [
        "api.contaazul.com",
        "attachments.contaazul.com",
        "cdn.contaazul.com",
    ]
    if not any(parsed.netloc.endswith(d) for d in allowed_domains):
        logger.error(f"Domínio não permitido: {parsed.netloc}")
        return False
    
    # 3. Bloquear IPs privados
    try:
        ip = ipaddress.ip_address(parsed.hostname or "")
        if ip.is_private or ip.is_loopback:
            logger.error(f"IP privado/loopback rejeitado: {ip}")
            return False
    except ValueError:
        pass  # É hostname, OK
    
    return True
```

**Testes de Segurança:**

```bash
pytest tests/test_security_ssrf.py -v

# Testes:
# - test_ssrf_localhost → bloqueia localhost
# - test_ssrf_private_ip → bloqueia 192.168.x.x
# - test_ssrf_metadata → bloqueia 169.254.169.254
# - test_ssrf_valid_domain → aceita contaazul.com
```

---

## 🚫 Rate Limiting

### Implementação

**Backoff exponencial** com `tenacity`:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.HTTPStatusError),
)
async def get_account_info(self, access_token: str):
    # Se 429, aguarda 2s, 4s, 8s...
    response = await client.get("/v1/account")
    response.raise_for_status()
    return response.json()
```

### Configuração

```env
# .env (não exposto, mas configurável no código)
MAX_RETRIES=3
BACKOFF_MULTIPLIER=1
BACKOFF_MIN=2
BACKOFF_MAX=10
```

---

## 🐳 Docker Security

### Usuário Não-Root

```dockerfile
# Dockerfile
RUN adduser --disabled-password --gecos '' appuser

USER appuser

# Container roda como uid=1000, não root
```

Verificar:
```bash
docker-compose exec api whoami
# Output: appuser
```

### Multi-Stage Build

```dockerfile
# Stage 1: Build
FROM python:3.10-slim as builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime (menor imagem)
FROM python:3.10-slim
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
```

### Secrets não no Dockerfile

```dockerfile
# ❌ NUNCA
ENV MASTER_KEY=abc123...

# ✅ Sempre via .env ou Docker secrets
# (não fica na imagem)
```

### Healthcheck

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1
```

---

## 🔐 Cloudflare Access (SSO)

### Como Funciona

1. Usuário acessa `https://payflow.seu-dominio.com`
2. Cloudflare intercepta e exige login Google
3. Após autenticar, Cloudflare libera acesso ao backend
4. Backend não precisa implementar autenticação

### Configurar Emails Autorizados

```
Cloudflare → Zero Trust → Access → Applications
├─ Editar "PayFlow API"
├─ Policies → Edit
└─ Include:
   └─ Emails: admin@dominio.com, dev@dominio.com
```

### Bypass Local (Desenvolvimento)

Para testar sem Cloudflare:

```bash
# Acessar diretamente
curl http://localhost:8000/healthz

# Ou no browser
http://localhost:8000/docs
```

---

## 🔍 Auditoria de Segurança

### Checklist

- [ ] `MASTER_KEY` tem 32 bytes
- [ ] `.env` está no `.gitignore`
- [ ] Logs não mostram tokens em plaintext
- [ ] SMTP usa TLS (`SMTP_USE_TLS=true`)
- [ ] OAuth usa HTTPS (`CONTA_AZUL_REDIRECT_URI` é https://)
- [ ] Cloudflare Access ativo em produção
- [ ] Docker roda como não-root (`USER appuser`)
- [ ] Backup do banco configurado
- [ ] SSRF validation ativa
- [ ] Rate limiting configurado

### Ferramentas

**Scan de Dependências:**
```bash
# Verificar CVEs
pip install safety
safety check -r requirements.txt
```

**Scan de Secrets:**
```bash
# Verificar secrets vazados
git secrets --scan

# Ou: truffleHog
trufflehog git file://. --only-verified
```

**Scan de Container:**
```bash
# Trivy
trivy image payflow-api:latest
```

---

## 🚨 Incidentes de Segurança

### Se MASTER_KEY vazar

**1. Rotacionar imediatamente:**
```bash
# Ver seção "Rotação de MASTER_KEY" acima
```

**2. Invalidar tokens OAuth2:**
```bash
docker-compose exec api bash

sqlite3 data/payflow.db
sqlite> DELETE FROM oauth_tokens;
sqlite> .quit
```

**3. Re-autorizar contas:**
```
Browser: https://payflow.seu-dominio.com/connect
# Cada usuário precisa re-autorizar
```

### Se SMTP_PASSWORD vazar

**1. Trocar senha:**
- Gmail: myaccount.google.com/apppasswords → revogar e gerar novo
- SendGrid: dashboard → revocar API key e criar nova

**2. Atualizar .env:**
```env
SMTP_PASSWORD=nova_senha_gerada
```

**3. Reiniciar:**
```bash
docker-compose restart api
```

### Se CLOUDFLARE_TUNNEL_TOKEN vazar

**1. Revogar tunnel:**
```
Cloudflare → Zero Trust → Tunnels
├─ Editar "payflow-api"
└─ Delete tunnel
```

**2. Criar novo tunnel:**
```
Tunnels → Create tunnel (gerar novo token)
```

**3. Atualizar .env e reiniciar:**
```bash
nano .env  # Atualizar CLOUDFLARE_TUNNEL_TOKEN
docker-compose down
docker-compose up -d
```

---

## 📚 Recursos

### Documentação
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [Fernet Spec](https://github.com/fernet/spec/blob/master/Spec.md)

### Ferramentas
- [safety](https://pypi.org/project/safety/) - Scan de dependências
- [bandit](https://bandit.readthedocs.io/) - SAST para Python
- [trivy](https://trivy.dev/) - Scan de containers
- [truffleHog](https://github.com/trufflesecurity/trufflehog) - Scan de secrets

---

## 🆘 Contato de Segurança

Para reportar vulnerabilidades:
- Email: security@seu-dominio.com
- PGP Key: (adicionar se disponível)
- Bug Bounty: (se aplicável)

**Por favor, não abra issues públicas para vulnerabilidades críticas.**

---

**Última atualização**: 2026-02-10

