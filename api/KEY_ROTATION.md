# 🔑 Key Rotation - Guia Operacional

## Visão Geral

Procedimento para rotacionar MASTER_KEY sem perder dados criptografados.

**Quando fazer**:
- Anualmente (best practice)
- Após suspeita de comprometimento
- Como parte de disaster recovery

**Tempo estimado**: 10-15 minutos

---

## 📋 Pré-requisitos

- Acesso ao servidor
- Docker e Docker Compose funcionando
- Backup atual do banco de dados
- Chave Vault/Secrets Manager disponível

---

## 🔄 Procedimento de Rotação

### 1. Gerar Nova MASTER_KEY

```bash
# Opção A: Python
python3 -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

# Opção B: OpenSSL
openssl rand -base64 32

# Opção C: Online (para teste apenas)
# https://www.random.org/bytes/
```

**Salvar output como**: `NEW_MASTER_KEY`

Exemplo:
```
NEW_MASTER_KEY=aBcDeFgHiJkLmNoPqRsTeVwXyZ1234567890+/===
```

---

### 2. Backup do Banco Atual

```bash
# No servidor
cd ~/payflow/api

# Fazer backup
cp data/payflow.db data/payflow.db.backup.$(date +%Y%m%d_%H%M%S)

# Verificar
ls -lh data/payflow.db*
```

---

### 3. Atualizar .env

```bash
nano .env  # ou seu editor
```

**Adicionar OLD_MASTER_KEYS e atualizar MASTER_KEY**:

```env
# Keys antigas (para backward compatibility)
OLD_MASTER_KEYS=<ANTIGA_MASTER_KEY>

# Nova key
MASTER_KEY=<NEW_MASTER_KEY>
```

**Salvar**: Ctrl+O, Enter, Ctrl+X

---

### 4. Verificar .env

```bash
# Verificar que está correto (sem expor keys)
grep -E "MASTER_KEY|OLD_MASTER_KEYS" .env
```

Esperado:
```
OLD_MASTER_KEYS=aBcDeFgHi...
MASTER_KEY=1234567890ab...
```

---

### 5. Rebuild Docker Image

```bash
# Parar containers
docker-compose down

# Rebuild com nova config
docker-compose build --no-cache

# Rodar novamente
docker-compose up -d
```

---

### 6. Verificar Logs

```bash
# Verificar se API iniciou corretamente
docker-compose logs api | grep -i "crypto\|initialized\|error"

# Esperado:
# INFO: Crypto inicializado com chave v1
```

---

### 7. Teste de Decriptação

```bash
# Entrar no container
docker-compose exec api bash

# Testar decriptação com chave antiga
python3 << 'EOF'
from app.crypto import get_crypto_manager
from app.database import init_db
from app.config import get_settings

settings = get_settings()
db_session = init_db(settings.DATABASE_URL)[1]()

# Buscar um token criptografado
token_record = db_session.query(OAuthToken).first()

if token_record:
    crypto = get_crypto_manager()
    plaintext = crypto.decrypt(token_record.access_token)
    print(f"✅ Decriptação OK: {plaintext[:20]}...")
else:
    print("Nenhum token encontrado")
EOF
```

---

### 8. (Opcional) Re-criptografar Todos os Tokens

Para não manter OLD_MASTER_KEYS indefinidamente, re-criptografar com nova key:

```bash
# Entrar no container
docker-compose exec api bash

python3 << 'EOF'
from app.crypto import get_crypto_manager
from app.database import init_db, OAuthToken
from app.config import get_settings

settings = get_settings()
engine, SessionLocal = init_db(settings.DATABASE_URL)
db = SessionLocal()

crypto = get_crypto_manager()

# Para cada token, descriptografar e re-criptografar
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

# Salvar
db.commit()
print(f"✅ Total: {len(tokens)} tokens re-criptografados")
EOF
```

---

### 9. Remover OLD_MASTER_KEYS (Após 24h)

Após confirmar que tudo está funcionando:

```bash
# Editar .env
nano .env

# Remover ou comentar:
# OLD_MASTER_KEYS=...

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## ✅ Checklist Pós-Rotação

- [ ] Nova MASTER_KEY gerada
- [ ] Backup do banco feito
- [ ] .env atualizado (MASTER_KEY + OLD_MASTER_KEYS)
- [ ] Docker rebuilt e containers rodando
- [ ] Logs sem erros (crypto inicializado)
- [ ] Teste de decriptação passou
- [ ] Tokens re-criptografados (opcional)
- [ ] OLD_MASTER_KEYS removido (após 24h)
- [ ] Backup de segurança em local remoto

---

## 🆘 Troubleshooting

### Erro: "MASTER_KEY inválido"
```
Solução:
1. Verificar .env (MASTER_KEY = 32 bytes base64)
2. Verificar que não há espaços extras
3. Verificar encoding (deve ser base64)
```

### Erro: "Não consegue decriptografar"
```
Solução:
1. Verificar que OLD_MASTER_KEYS está correto
2. Verificar que não foram misturadas as keys
3. Restaurar backup se necessário:
   cp data/payflow.db.backup.YYYYMMDD_HHMMSS data/payflow.db
```

### Tokens corrompidos
```
Solução:
1. Docker down
2. Restaurar backup
3. Reverter .env para MASTER_KEY anterior
4. Docker up
5. Investigar o que deu errado
```

---

## 📊 Exemplo: Rotação Completa

```bash
# 1. Gerar nova key
python3 -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
# Output: aBcDeFgHiJkLmNoPqRsTeVwXyZ1234567890+/===

# 2. Backup
cp data/payflow.db data/payflow.db.backup.20260210_143000

# 3. Atualizar .env
OLD_MASTER_KEYS=<ANTIGA>
MASTER_KEY=aBcDeFgHiJkLmNoPqRsTeVwXyZ1234567890+/===

# 4. Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 5. Verificar logs
docker-compose logs api | head -20

# 6. Teste de decriptação
docker-compose exec api python3 -c "..."

# 7. Re-criptografar (opcional)
docker-compose exec api python3 << 'EOF'
...
EOF

# 8. Remover OLD_MASTER_KEYS (após 24h)
nano .env  # remover OLD_MASTER_KEYS
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 9. Verificar
docker-compose ps
docker-compose logs api | grep crypto
```

---

## 📚 Referências

- [Cryptography Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [Key Management](https://www.cloudflare.com/learning/ssl/key-management/)
- [Fernet Documentation](https://cryptography.io/en/latest/fernet/)

---

**Última atualização**: 2026-02-10
**Responsável**: DevOps/Security Team

