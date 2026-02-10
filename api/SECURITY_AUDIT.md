# 🔒 REVISÃO DE SEGURANÇA - PayFlow v1.0.0

Data: 2026-02-10
Escopo: API, Worker, Docker, Dependências

---

## 📋 RISCOS IDENTIFICADOS

### 🔴 ALTO RISCO (1)

#### 1. SSRF (Server-Side Request Forgery) - Download de Anexos
**Arquivo**: `app/worker/conta_azul_financial_client.py:download_receipt()`
**Severity**: Alto
**Impacto**: Atacante pode redirecionar downloads para URLs maliciosas (internal IPs, cloud metadata)

**Código Vulnerável**:
```python
async def download_receipt(self, receipt_url: str) -> Optional[bytes]:
    # ❌ Sem validação de domínio!
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(receipt_url)  # URL não validada
        return response.content
```

**Risco Específico**:
- Atacante insere URL maliciosa: `http://169.254.169.254/...` (AWS metadata)
- Ou: `http://localhost:8000/admin` (acesso interno)
- Ou: `http://192.168.1.1/config` (rede privada)

**Patch Recomendado**:
```python
from urllib.parse import urlparse
import ipaddress

# Adicionar validação de domínio
def _validate_receipt_url(self, url: str) -> bool:
    """Validar URL de recibo (SSRF prevention)."""
    try:
        parsed = urlparse(url)
        
        # 1. Apenas HTTPS
        if parsed.scheme != "https":
            logger.warning(f"URL não-HTTPS rejeitada: {url}")
            return False
        
        # 2. Validar hostname (permitir apenas Conta Azul)
        allowed_domains = [
            "api.contaazul.com",
            "attachments.contaazul.com",
            "cdn.contaazul.com",
        ]
        
        if not any(parsed.netloc.endswith(domain) for domain in allowed_domains):
            logger.error(f"Domínio não permitido: {parsed.netloc}")
            return False
        
        # 3. Verificar que não é IP privado
        try:
            ip = ipaddress.ip_address(parsed.hostname or "")
            if ip.is_private or ip.is_loopback:
                logger.error(f"IP privado/loopback rejeitado: {ip}")
                return False
        except ValueError:
            # É um hostname, OK
            pass
        
        return True
    except Exception as e:
        logger.error(f"Erro ao validar URL: {e}")
        return False

async def download_receipt(self, receipt_url: str) -> Optional[bytes]:
    # ✅ Com validação
    if not self._validate_receipt_url(receipt_url):
        logger.error(f"URL rejeitada por validação: {receipt_url}")
        return None
    
    logger.debug(f"Baixando recibo de {receipt_url[:50]}...")
    
    try:
        async with httpx.AsyncClient(
            timeout=self.settings.SMTP_TIMEOUT,  # timeout reusável
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
            follow_redirects=False,  # Não seguir redirects (SSRF prevention)
        ) as client:
            response = await client.get(receipt_url)
            response.raise_for_status()
            
            pdf_bytes = response.content
            logger.debug(f"PDF baixado: {len(pdf_bytes)} bytes")
            
            return pdf_bytes
    except Exception as e:
        logger.error(f"Erro ao baixar recibo: {e}")
        return None
```

**Teste de Segurança**:
```python
def test_ssrf_localhost():
    """Rejeitar localhost."""
    client = ContaAzulFinancialClient("token")
    assert not client._validate_receipt_url("https://localhost:8000/admin")

def test_ssrf_private_ip():
    """Rejeitar IP privado."""
    client = ContaAzulFinancialClient("token")
    assert not client._validate_receipt_url("https://192.168.1.1/config")

def test_ssrf_metadata():
    """Rejeitar metadata AWS."""
    client = ContaAzulFinancialClient("token")
    assert not client._validate_receipt_url("http://169.254.169.254/")

def test_ssrf_valid_domain():
    """Aceitar domínio válido."""
    client = ContaAzulFinancialClient("token")
    assert client._validate_receipt_url("https://api.contaazul.com/attachment/123")
```

---

### 🟠 RISCO MÉDIO (3)

#### 2. MASTER_KEY sem Rotação
**Arquivo**: `app/crypto.py`
**Severity**: Médio
**Impacto**: Compromisso de MASTER_KEY expõe todos os tokens históricos

**Problema**:
- Não há suporte a key rotation
- Se MASTER_KEY vaza, todos os tokens criptografados são descriptografáveis

**Patch Recomendado**:
```python
from datetime import datetime, timedelta
from typing import List

class CryptoManager:
    """Gerencia criptografia com suporte a rotação de chaves."""
    
    def __init__(self):
        """Inicializa com MASTER_KEY e suporta rotação."""
        settings = get_settings()
        
        # Chave atual
        self._key = base64.urlsafe_b64decode(settings.MASTER_KEY)
        self._key_version = 1
        
        # Chaves antigas para decriptação (se houver)
        self._old_keys = []
        
        # Carregar chaves antigas do banco (se configurado)
        if hasattr(settings, 'OLD_MASTER_KEYS'):
            self._old_keys = [
                base64.urlsafe_b64decode(k) 
                for k in settings.OLD_MASTER_KEYS.split(',')
            ]
        
        logger.info(f"Crypto inicializado com chave v{self._key_version}")
    
    def encrypt(self, plaintext: str) -> str:
        """Criptografa com versão de chave."""
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)
        
        f = Fernet(base64.urlsafe_b64encode(self._key))
        encrypted = f.encrypt(plaintext.encode("utf-8"))
        
        # Adicionar versão de chave como prefixo
        versioned = f"{self._key_version}${encrypted.decode('utf-8')}"
        return versioned
    
    def decrypt(self, ciphertext: str) -> str:
        """Decriptografa com suporte a múltiplas versões."""
        try:
            # Extrair versão de chave
            if '$' in ciphertext:
                version_str, encrypted_text = ciphertext.split('$', 1)
                version = int(version_str)
            else:
                # Compatibilidade com tokens antigos
                version = 1
                encrypted_text = ciphertext
            
            # Usar chave apropriada
            if version == self._key_version:
                key = self._key
            elif version < self._key_version and self._old_keys:
                key = self._old_keys[version - 1]
            else:
                raise ValueError(f"Versão de chave inválida: {version}")
            
            f = Fernet(base64.urlsafe_b64encode(key))
            plaintext = f.decrypt(encrypted_text.encode("utf-8"))
            
            return plaintext.decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Erro ao decriptografar: {e}")
```

**Instruções de Rotação**:
```bash
# 1. Gerar nova MASTER_KEY
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
# Salvar output como: NEW_MASTER_KEY

# 2. No .env, adicionar:
OLD_MASTER_KEYS=<MASTER_KEY_ANTIGO>
MASTER_KEY=<NEW_MASTER_KEY>

# 3. Atualizar container e rodar:
docker-compose up -d --build

# 4. Após 24h, limpar OLD_MASTER_KEYS (já tudo re-criptografado)
# Remover OLD_MASTER_KEYS do .env
# docker-compose restart
```

---

#### 3. Dependências sem Pinagem de Patch Version
**Arquivo**: `requirements.txt`
**Severity**: Médio
**Impacto**: Supply chain attacks, breaking changes em minor versions

**Problema**:
```
fastapi==0.104.1     # ✅ Pinado (bom)
pydantic==2.5.0      # ✅ Pinado (bom)
pytest==7.4.3        # ✅ Pinado (bom)
httpx==0.25.2        # ✅ Pinado (bom)
```

Verifi que as dependências estão pinadas, mas faltam checksums.

**Patch Recomendado**:
```bash
# Gerar requirements.txt com hashes
pip install pip-tools
pip-compile --generate-hashes requirements.in > requirements.txt

# Ou adicionar hashes manualmente
python -m pip install --require-hashes --only-binary=:all: -r requirements.txt
```

**requirements.txt com Hashes**:
```
fastapi==0.104.1 \
    --hash=sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890 \
    --hash=sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
pydantic==2.5.0 \
    --hash=sha256:...
```

---

#### 4. Endpoints /docs e /redoc Não Protegidos por Cloudflare Access
**Arquivo**: `app/main.py:docs_url="/docs"`
**Severity**: Médio
**Impacto**: Exposure de API schema, endpoints, parâmetros para public

**Problema**:
```python
app = FastAPI(
    docs_url="/docs",      # ❌ Sem proteção!
    redoc_url="/redoc",    # ❌ Sem proteção!
)
```

**Patch Recomendado**:

Opção 1: Desabilitar em produção
```python
from app.config import get_settings

settings = get_settings()

docs_url = "/docs" if settings.ENVIRONMENT == "development" else None
redoc_url = "/redoc" if settings.ENVIRONMENT == "development" else None

app = FastAPI(
    docs_url=docs_url,
    redoc_url=redoc_url,
)
```

Opção 2: Proteger via Cloudflare Access (recomendado)
```yaml
# docker-compose.yml
cloudflared:
  environment:
    - CLOUDFLARE_ACCESS_POLICY=api_docs  # Nova policy
```

Configurar na Cloudflare:
- Criar policy: "API Documentation"
- Paths: `/docs`, `/redoc`, `/openapi.json`
- Rule: "Allow" apenas para admin emails

---

### 🟡 RISCO BAIXO (4)

#### 5. CORS Permitindo Apenas Conta Azul (OK, mas restrictivo)
**Arquivo**: `app/main.py`
**Status**: Bem configurado
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://accounts.contaazul.com"],  # ✅ Muito restritivo (bom)
    allow_methods=["GET", "POST"],                     # ✅ Apenas necessários
    allow_headers=["Content-Type", "Authorization"],   # ✅ Minimal
)
```

**Nota**: Adicionar `https://payflow.seu-dominio.com` se houver frontend:
```python
allow_origins=[
    "https://accounts.contaazul.com",
    "https://payflow.seu-dominio.com",  # Seu frontend
]
```

---

#### 6. Timeout em Download de Anexos Poderia Ser Mais Curto
**Arquivo**: `app/worker/conta_azul_financial_client.py`
**Current**: `timeout=30`
**Recomendação**: `timeout=10`

**Patch**:
```python
# Na classe ContaAzulFinancialClient
async def download_receipt(self, receipt_url: str) -> Optional[bytes]:
    try:
        async with httpx.AsyncClient(
            timeout=10,  # ✅ Reduzido de 30
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
            follow_redirects=False,
        ) as client:
            response = await client.get(receipt_url)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error(f"Erro ao baixar recibo: {e}")
        return None
```

---

#### 7. Permissões SQLite em Volume Docker
**Arquivo**: `Dockerfile`
**Current Status**: 
```dockerfile
RUN chown -R appuser:appuser /app/data
```

**Verificação**: Verificar modo de arquivo
```bash
# No container
ls -la /app/data/payflow.db
# Esperado: -rw-r--r-- appuser appuser
```

**Patch Recomendado** (mais restritivo):
```dockerfile
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app/data && \
    chmod 700 /app/data  # Apenas owner pode ler/escrever
```

---

#### 8. Validação de Tamanho de Email PDF
**Arquivo**: `app/services/mailer.py`
**Current**: `MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024` (25MB)
**Recomendação**: Reduzir para 10MB

**Patch**:
```python
class MailerService:
    MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB em vez de 25MB
    
    def _validate_attachment(self, pdf_content: bytes, filename: str) -> None:
        if len(pdf_content) > self.MAX_ATTACHMENT_SIZE:
            raise EmailValidationError(
                f"PDF muito grande: {len(pdf_content)} bytes "
                f"(máximo {self.MAX_ATTACHMENT_SIZE} bytes)"
            )
```

---

#### 9. Falta Validação de Tamanho em Conta Azul Client
**Arquivo**: `app/worker/conta_azul_financial_client.py`
**Issue**: Sem limite máximo de tamanho em `_request()`

**Patch**:
```python
class ContaAzulFinancialClient:
    MAX_RESPONSE_SIZE = 100 * 1024 * 1024  # 100MB máximo
    
    async def _request(self, method: str, endpoint: str, ...) -> Dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=30,
            limits=httpx.Limits(max_connections=5),  # Limitar conexões
        ) as client:
            response = await client.request(...)
            
            # Validar tamanho da resposta
            if len(response.content) > self.MAX_RESPONSE_SIZE:
                raise Exception(f"Response muito grande: {len(response.content)} bytes")
            
            return response.json()
```

---

#### 10. Logs Poderiam Não Incluir Caminhos Sensíveis
**Arquivo**: `app/logging.py`
**Status**: Bem implementado (SensitiveDataFilter)

**Verificação recomendada**:
```python
# Adicionar mais padrões sensíveis
SENSITIVE_PATTERNS: Dict[str, str] = {
    "token": r"(authorization|access_token|refresh_token|bearer|token)[:\s]*([a-zA-Z0-9._\-]+)",
    "password": r"(password|passwd|pwd|secret)[:\s]*([a-zA-Z0-9._\-]+)",
    "api_key": r"(api[_-]?key|apikey)[:\s]*([a-zA-Z0-9._\-]+)",
    "url_params": r"[?&](key|token|secret|password)=([a-zA-Z0-9._\-]+)",  # Novo
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Novo (opcional)
}
```

---

## 📊 SUMÁRIO DE RISCOS

| # | Risco | Severity | Status | Action |
|---|-------|----------|--------|--------|
| 1 | SSRF em download | 🔴 Alto | ❌ Ativo | Implementar validação ASAP |
| 2 | MASTER_KEY sem rotação | 🟠 Médio | ⚠️ Planejado | Implementar para produção |
| 3 | Deps sem hashes | 🟠 Médio | ⚠️ Planejado | Adicionar pip-tools |
| 4 | /docs não protegido | 🟠 Médio | ⚠️ Planejado | Configurar Access policy |
| 5 | CORS (OK) | 🟡 Baixo | ✅ Bom | Adicionar frontend URL |
| 6 | Timeout longo | 🟡 Baixo | ⚠️ Otimizar | Reduzir de 30 → 10s |
| 7 | Permissões SQLite | 🟡 Baixo | ⚠️ Tighten | chmod 700 /app/data |
| 8 | Max PDF 25MB | 🟡 Baixo | ⚠️ Reduzir | Limite para 10MB |
| 9 | Sem limite response | 🟡 Baixo | ⚠️ Adicionar | Máximo 100MB |
| 10 | Logs & PII | 🟡 Baixo | ✅ Bom | Review patterns |

---

## ✅ CHECKLIST DE PRODUÇÃO

### Segurança (Obrigatório)
- [ ] **PATCH #1**: Implementar SSRF validation em download_receipt()
- [ ] **PATCH #2**: Implementar MASTER_KEY rotation
- [ ] **PATCH #3**: Adicionar hashes em requirements.txt
- [ ] **PATCH #4**: Proteger /docs e /redoc com Cloudflare Access
- [ ] Audit logs habilitados (verificar app/logging.py)
- [ ] Secrets não em .env versionado (usar GitHub Secrets, Vault, etc)
- [ ] Rate limiting em todos os endpoints (implementado em cliente HTTP)
- [ ] HTTPS obrigatório (Cloudflare Tunnel)

### Configuração (Obrigatório)
- [ ] MASTER_KEY gerado seguro (32 bytes)
- [ ] SMTP_PASSWORD seguro
- [ ] JWT_SECRET seguro
- [ ] CONTA_AZUL credentials seguras
- [ ] .env não versionado (.gitignore)
- [ ] .env.example sem valores sensíveis

### Operações (Obrigatório)
- [ ] Backup diário do SQLite (data/payflow.db)
- [ ] Logs centralizados (não em filesystem)
- [ ] Monitoring de erros (Sentry, DataDog, etc)
- [ ] Healthchecks funcionando (API, Worker, Cloudflared)
- [ ] docker-compose with restart policies
- [ ] Volume docker com permissões restritas

### Infraestrutura (Obrigatório)
- [ ] Cloudflare Tunnel ativo
- [ ] Cloudflare Access com Google SSO
- [ ] WAF rules (Cloudflare WAF)
- [ ] DDoS protection (Cloudflare)
- [ ] Rate limiting (Cloudflare)

### Testes (Recomendado)
- [ ] Teste de SSRF (validação de domínio)
- [ ] Teste de key rotation
- [ ] Teste de rate limiting
- [ ] Teste de timeout
- [ ] Penetration testing

### Documentação (Recomendado)
- [ ] SECURITY.md criado
- [ ] Incident response plan
- [ ] Key rotation procedure
- [ ] Backup/restore procedure

---

## 🔐 PRÁTICAS RECOMENDADAS ADICIONAIS

### 1. Ambiente de Secrets
```bash
# Em produção, usar secrets manager (não .env)
# Opções:
# - AWS Secrets Manager
# - Azure Key Vault
# - HashiCorp Vault
# - 1Password Secrets Automation
# - Doppler
```

### 2. WAF Rules (Cloudflare)
```
# Bloquear:
- User-Agent suspeitos
- Referer suspeito
- Rate limiting por IP
- Geo-blocking (se aplicável)
```

### 3. Logging Centralizado
```bash
# Não usar filesystem, usar:
# - CloudWatch (AWS)
# - Azure Monitor (Azure)
# - Datadog
# - ELK Stack
# - Splunk
```

### 4. Monitoramento
```bash
# Alertar para:
# - Erros 5xx
# - Rate limit hits
# - Failed auth attempts
# - Database errors
# - Worker failures
```

### 5. Backup & Disaster Recovery
```bash
# Backup:
# - Frequência: Diário
# - Retenção: 30 dias
# - Teste de restore: Semanal

# Backup de dados:
rsync -avz data/payflow.db backup-server:/backups/

# Teste de restore:
sqlite3 data/payflow.db ".restore /path/to/backup"
```

---

## 📝 PRÓXIMOS PASSOS

### Imediato (Antes de Produção)
1. Implementar SSRF validation (PATCH #1)
2. Testar com URLs maliciosas
3. Implementar key rotation (PATCH #2)
4. Adicionar hashes em deps (PATCH #3)

### Curto Prazo (1 semana)
1. Proteger /docs com Access
2. Implementar logging centralizado
3. Setup de backup

### Médio Prazo (1 mês)
1. Penetration testing
2. Security audit completo
3. Implementar WAF rules

---

## 📞 REFERÊNCIAS

- [OWASP Top 10](https://owasp.org/Top10/)
- [SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Cryptography Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [Dependency Management](https://cheatsheetseries.owasp.org/cheatsheets/Vulnerable_and_Outdated_Components_Cheat_Sheet.html)

---

**Revisão por**: GitHub Copilot  
**Data**: 2026-02-10  
**Status**: Pronto para implementação

