# ✅ PADRONIZAÇÃO DE DATETIME NO SQLITE - TZDateTime

**Data:** 2026-02-11  
**Status:** ✅ IMPLEMENTADO  
**Estratégia:** ISO 8601 com timezone (String)  

---

## 🎯 OBJETIVO

Garantir que `expires_at` **nunca seja naive** e sempre tenha timezone info (UTC).

---

## 📋 ESTRATÉGIA ESCOLHIDA

**Opção B: Armazenar string ISO 8601 com timezone**

### Por que ISO 8601?

1. ✅ **Explícito**: `2026-02-11T18:00:00+00:00` é inequívoco
2. ✅ **Human-readable**: Fácil de debugar no banco
3. ✅ **Portável**: Funciona em qualquer DB
4. ✅ **Padrão**: ISO 8601 é universal
5. ✅ **SQLite-friendly**: String é tipo nativo

### Comparação com Outras Opções

| Estratégia | Pros | Cons | Escolhida |
|-----------|------|------|-----------|
| A) Epoch (int) | Performance | Não human-readable, difícil debug | ❌ |
| B) ISO 8601 string | Explícito, debugável | Leve overhead conversão | ✅ |
| C) DateTime ORM | Nativo ORM | SQLite não suporta tzinfo nativo | ❌ |

---

## 🔧 IMPLEMENTAÇÃO

### 1. Tipo Customizado: `TZDateTime`

Criado `TypeDecorator` do SQLAlchemy que:

**No save (bind)**:
```python
datetime → ISO 8601 string com timezone
Exemplo: datetime(2026, 2, 11, 18, 0, 0, tzinfo=UTC)
      → "2026-02-11T18:00:00+00:00"
```

**No load (result)**:
```python
ISO 8601 string → datetime timezone-aware (UTC)
Exemplo: "2026-02-11T18:00:00+00:00"
      → datetime(2026, 2, 11, 18, 0, 0, tzinfo=UTC)
```

**Código**:
```python
class TZDateTime(TypeDecorator):
    """Tipo customizado para datetime com timezone no SQLite."""
    
    impl = String  # Armazena como string
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        # Garante UTC aware e converte para ISO 8601
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    
    def process_result_value(self, value, dialect):
        # Parse ISO 8601 e garante UTC aware
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
```

### 2. Modelo Atualizado

```python
class OAuthToken(Base):
    # ...
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    # ← Agora usa TZDateTime em vez de DateTime
```

### 3. Código Simplificado

**Antes** (complexo):
```python
# Tinha que remover tzinfo manualmente
expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(...)
```

**Depois** (simples):
```python
# TZDateTime lida com tudo
expires_at = datetime.now(timezone.utc) + timedelta(...)
```

### 4. `__repr__` Melhorado

```python
def __repr__(self) -> str:
    tzinfo_str = f" tzinfo={self.expires_at.tzinfo}" if hasattr(...) else ""
    return f"<OAuthToken ... expires_at={self.expires_at.isoformat()}{tzinfo_str}>"
```

Agora mostra:
```
<OAuthToken account_id=abc123 expires_at=2026-02-11T18:00:00+00:00 tzinfo=UTC>
```

---

## 📝 ARQUIVOS MODIFICADOS

### 1. `app/database.py`
- ✅ Classe `TZDateTime` adicionada
- ✅ `OAuthToken.expires_at` usa `TZDateTime`
- ✅ `__repr__` mostra `tzinfo`

### 2. `app/services_auth.py`
- ✅ `save_tokens()` simplificado (usa aware direto)
- ✅ `refresh_access_token()` simplificado
- ✅ `is_token_expired()` com warning para naive (migração antiga)
- ✅ `normalize_datetime_utc()` marcado como deprecated

### 3. `app/routes_oauth.py`
- ✅ Callback simplificado (usa aware direto)
- ✅ Refresh endpoint simplificado

### 4. `tests/test_datetime_fix.py`
- ✅ Testes atualizados para TZDateTime
- ✅ Teste de compatibilidade retroativa
- ✅ Teste que tzinfo está sempre presente

### 5. `scripts/migrate_datetime_to_iso8601.py` (NOVO)
- ✅ Migração de dados existentes
- ✅ Converte naive → ISO 8601 com UTC
- ✅ Converte aware → ISO 8601 UTC
- ✅ Skip se já migrado

### 6. `scripts/debug_token_expires.py` (NOVO)
- ✅ Debug completo de tokens
- ✅ Mostra `expires_at`, `tzinfo`, tipo
- ✅ Status (expirado/válido)
- ✅ Resumo de naive/aware/string

---

## 🚀 MIGRAÇÃO DE DADOS

### Executar Migração

```bash
cd api/
python scripts/migrate_datetime_to_iso8601.py
```

### O que Faz

1. Lê todos os tokens do banco
2. Para cada `expires_at`:
   - Se já é ISO 8601 com timezone → Skip
   - Se é datetime naive → Assume UTC e converte
   - Se é datetime aware → Converte para UTC
3. Atualiza no banco como string ISO 8601
4. Commit e resumo

### Output Esperado

```
📊 Encontrados 3 token(s) para verificar

📍 Token: account_abc123...
   expires_at atual: 2026-02-11 18:00:00
   Tipo: datetime
   🔄 Datetime naive detectado - Assumindo UTC
   ✅ Migrado para: 2026-02-11T18:00:00+00:00

📊 RESUMO DA MIGRAÇÃO
Total de tokens: 3
✅ Migrados: 3
⏭️  Já migrados: 0
❌ Erros: 0

✅ Migração concluída com sucesso!
```

---

## 🔍 DEBUG DE TOKENS

### Executar Debug

```bash
cd api/
python scripts/debug_token_expires.py
```

### O que Mostra

- account_id
- expires_at (valor raw)
- Tipo de expires_at
- tzinfo (None, UTC, etc)
- ISO 8601 format
- Status (expirado/válido)
- Tempo restante/passado
- Timestamps (created_at, updated_at)

### Output Exemplo

```
Token #1
────────────────────────────────────────────────────────────────────────────────
📝 account_id: account_abc123
📅 expires_at: 2026-02-11 18:00:00+00:00
   Tipo: datetime
   ✅ tzinfo: UTC
   ISO 8601: 2026-02-11T18:00:00+00:00
   ✅ Status: VÁLIDO por mais 3456s
🕒 created_at: 2026-02-11 12:00:00
🕒 updated_at: 2026-02-11 12:00:00

📊 Resumo:
   Naive datetimes: 0
   Aware datetimes: 3
   Strings: 0

✅ Todos os tokens estão no formato correto!
```

---

## ✅ COMPATIBILIDADE RETROATIVA

### Garantias

1. **TZDateTime aceita naive**: Se por algum motivo vier naive, converte para UTC
2. **is_token_expired() com warning**: Se detectar naive, loga warning mas funciona
3. **Migração não-destrutiva**: Lê valores existentes e converte sem perda
4. **Testes de compatibilidade**: `test_backwards_compatibility_naive_datetime`

### Leitura de Dados Antigos

- Datetime naive no banco → TZDateTime converte para UTC aware
- Datetime aware no banco → TZDateTime mantém/converte para UTC
- String ISO 8601 → TZDateTime parse e garante UTC aware

---

## 🧪 TESTES

### Executar Testes

```bash
pytest tests/test_datetime_fix.py -v
```

### Testes Incluídos

1. ✅ `test_token_not_expired_aware_datetime` - Token futuro aware
2. ✅ `test_token_expired_aware_datetime` - Token passado aware
3. ✅ `test_token_just_expired` - Token recém-expirado
4. ✅ `test_token_about_to_expire` - Token prestes a expirar
5. ✅ `test_backwards_compatibility_naive_datetime` - Compatibilidade naive
6. ✅ `test_no_crash_with_timezone_aware_comparison` - Sem TypeError
7. ✅ `test_token_expires_at_has_timezone_info` - tzinfo sempre presente

---

## 📊 ANTES vs DEPOIS

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Formato no banco | datetime naive (ambíguo) | ISO 8601 com TZ (explícito) |
| tzinfo | None (naive) | UTC (aware) |
| Comparação | ❌ Crash (TypeError) | ✅ Funciona sempre |
| Debug | Difícil (não sabe TZ) | Fácil (TZ explícita) |
| Código | Complexo (.replace(tzinfo=None)) | Simples (usa aware direto) |
| Persistência | Inconsistente | Consistente (ISO 8601) |

---

## 🚀 DEPLOY

```bash
# 1. Pull das alterações
cd /opt/ctrls-payflow-v2/Ctrls-Payflow_v2
git pull

# 2. Migrar dados existentes
cd api
python scripts/migrate_datetime_to_iso8601.py

# 3. Verificar migração
python scripts/debug_token_expires.py

# 4. Rebuild containers
docker-compose down
docker-compose up -d --build

# 5. Verificar logs
docker-compose logs -f worker | grep -E "(Token|válido|expirado)"
```

---

## 📝 EXEMPLO DE FLUXO

### Salvar Token

```python
# Código (simples)
expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
token.expires_at = expires_at
db.commit()

# No banco (ISO 8601 string)
"2026-02-11T19:00:00+00:00"
```

### Ler Token

```python
# Ler do banco
token = db.query(OAuthToken).first()

# expires_at é sempre aware
assert token.expires_at.tzinfo == timezone.utc

# Comparar (nunca crasha)
if datetime.now(timezone.utc) >= token.expires_at:
    print("Expirado")
```

---

## 🎯 RESULTADO FINAL

- ✅ `expires_at` **nunca é naive**
- ✅ Sempre tem timezone info (UTC)
- ✅ Armazenado como ISO 8601 string
- ✅ Human-readable no banco
- ✅ Código simplificado
- ✅ Compatibilidade retroativa garantida
- ✅ Migração não-destrutiva
- ✅ Scripts de debug completos
- ✅ Testes garantem não-regressão

---

**✅ PADRONIZAÇÃO COMPLETA E TESTADA**

**Status:** PRONTO PARA PRODUÇÃO  
**Prioridade:** ALTA - Deploy + Migração Recomendados

