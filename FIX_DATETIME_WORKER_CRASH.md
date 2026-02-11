# Fix: Worker Crash - DateTime Naive/Aware Comparison

**Data:** 2026-02-11  
**Prioridade:** CRÍTICO  
**Status:** ✅ CORRIGIDO  

---

## 🐛 Problema

O worker estava crashando com o erro:

```python
TypeError: can't compare offset-naive and offset-aware datetimes
```

### Causa Raiz

- `is_token_expired()` compara `datetime.now(timezone.utc)` (aware) com `token.expires_at` (naive)
- SQLite não armazena timezone info nativamente
- Datetimes salvos no banco eram naive, mas comparação usava aware UTC

### Impacto

- ✅ Worker ficava unhealthy
- ✅ Tokens não eram renovados
- ✅ Sistema parava de processar contas a receber

---

## ✅ Solução Implementada

### 1. Função Helper: `normalize_datetime_utc()`

Criada função para normalizar datetimes, tratando tanto naive quanto aware:

```python
def normalize_datetime_utc(dt: datetime) -> datetime:
    """
    Normaliza datetime para UTC aware.
    
    SQLite não armazena timezone info nativamente, então precisamos
    garantir consistência ao salvar e ler datetimes.
    
    Args:
        dt: Datetime naive ou aware
        
    Returns:
        Datetime aware em UTC
    """
    if dt.tzinfo is None:
        # Naive datetime - assumir UTC
        return dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        # Aware mas não UTC - converter
        return dt.astimezone(timezone.utc)
    else:
        # Já é UTC aware
        return dt
```

### 2. Correção de `is_token_expired()`

Método agora usa `normalize_datetime_utc()` para lidar com ambos os casos:

```python
def is_token_expired(self, token: OAuthToken) -> bool:
    """
    Verifica se token está expirado.
    
    Trata datetimes naive (sem timezone) como UTC para compatibilidade
    com SQLite que não armazena timezone info nativamente.
    """
    now = datetime.now(timezone.utc)
    expires_at = normalize_datetime_utc(token.expires_at)
    
    is_expired = now >= expires_at
    
    if is_expired:
        logger.debug(f"Token expirado: now={now.isoformat()}, expires_at={expires_at.isoformat()}")
    else:
        time_remaining = expires_at - now
        logger.debug(f"Token válido por mais {time_remaining.total_seconds():.0f}s")
    
    return is_expired
```

### 3. Persistência Consistente

Todos os pontos onde `expires_at` é salvo agora usam **naive UTC** para compatibilidade com SQLite:

```python
# services_auth.py - save_tokens()
expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)

# services_auth.py - refresh_access_token()
token_record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)

# routes_oauth.py - callback
expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)

# routes_oauth.py - refresh_token_endpoint
token_record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)
```

### 4. Logs Melhorados

Adicionados logs informativos em `is_token_expired()`:

- Token expirado: mostra `now` e `expires_at` em ISO format
- Token válido: mostra tempo restante em segundos

---

## 🧪 Testes Criados

Arquivo: `tests/test_datetime_fix.py`

### Testes de `normalize_datetime_utc()`

1. ✅ `test_normalize_naive_datetime` - Naive → UTC aware
2. ✅ `test_normalize_utc_aware_datetime` - UTC aware → Inalterado
3. ✅ `test_normalize_non_utc_aware_datetime` - Outro timezone → UTC

### Testes de `is_token_expired()`

1. ✅ `test_token_not_expired_naive_datetime` - Token futuro naive
2. ✅ `test_token_expired_naive_datetime` - Token passado naive
3. ✅ `test_token_not_expired_aware_datetime` - Token futuro aware
4. ✅ `test_token_expired_aware_datetime` - Token passado aware
5. ✅ `test_token_just_expired` - Token que acabou de expirar
6. ✅ `test_token_about_to_expire` - Token prestes a expirar
7. ✅ `test_no_crash_with_naive_and_aware_comparison` - **Teste principal do bug**

---

## 📝 Arquivos Modificados

1. **`app/services_auth.py`**
   - Adicionada função `normalize_datetime_utc()`
   - Corrigido `is_token_expired()` para usar normalização
   - Corrigido `save_tokens()` para salvar naive UTC
   - Corrigido `refresh_access_token()` para salvar naive UTC
   - Logs melhorados

2. **`app/routes_oauth.py`**
   - Corrigido callback OAuth para salvar naive UTC
   - Corrigido refresh token endpoint para salvar naive UTC

3. **`tests/test_datetime_fix.py`** (NOVO)
   - 10 testes cobrindo todos os cenários
   - Teste específico para o bug original

---

## 🔍 Como Detectar o Problema

### Sintomas

```
TypeError: can't compare offset-naive and offset-aware datetimes
```

### Logs Esperados ANTES da Correção

```
ERROR | Worker crashed: TypeError: can't compare offset-naive and offset-aware datetimes
```

### Logs Esperados DEPOIS da Correção

```
DEBUG | Token válido por mais 3456s
INFO  | Token renovado com sucesso para account123...
```

---

## ✅ Validação

### Testes Unitários

```bash
# Rodar testes do fix
pytest tests/test_datetime_fix.py -v

# Rodar todos os testes
pytest tests/ -v
```

### Teste no Worker

```bash
# Verificar logs do worker
docker-compose logs -f worker

# Deve mostrar:
# ✅ Token válido por mais XXXs
# ✅ Processando conta YYY...
# ✅ Sem crashes
```

---

## 🚀 Deploy

### No Servidor

```bash
# 1. Pull das alterações
cd /opt/ctrls-payflow-v2/Ctrls-Payflow_v2
git pull

# 2. Rebuild containers
cd api
docker-compose down
docker-compose up -d --build

# 3. Monitorar worker
docker-compose logs -f worker | grep -E "(Token|expirado|válido)"
```

---

## 📊 Antes vs Depois

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Datetimes no banco | Inconsistente (aware/naive) | Consistente (naive UTC) |
| Comparação | ❌ Crash | ✅ Funciona |
| Worker health | ❌ Unhealthy | ✅ Healthy |
| Logs | ❌ Sem debug | ✅ Debug informativo |
| Testes | ❌ Não coberto | ✅ 10 testes |

---

## 🎯 Resultado

- ✅ Worker não crasha mais
- ✅ Comparação de datetimes funciona (naive e aware)
- ✅ Tokens são renovados corretamente
- ✅ Sistema continua processando sem interrupções
- ✅ Logs informativos para debugging
- ✅ Testes garantem não-regressão

---

## 🔧 Decisões Técnicas

### Por que Salvar como Naive UTC?

1. **SQLite nativo**: Não suporta timezone info
2. **Simplicidade**: Menos conversões desnecessárias
3. **Compatibilidade**: Funciona com código existente
4. **Consistência**: Todos os pontos usam a mesma estratégia

### Por que Normalizar na Leitura?

1. **Flexibilidade**: Aceita tanto naive quanto aware
2. **Migração suave**: Não quebra tokens existentes
3. **Robustez**: Trata diferentes cenários
4. **Debugging**: Logs mostram o que está acontecendo

---

**Desenvolvido:** 2026-02-11  
**Testado:** ✅ 10 testes passando  
**Prioridade:** CRÍTICO - Deploy Imediato Recomendado

