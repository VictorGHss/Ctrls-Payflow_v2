# 🚨 Quick Fix: Erro 401 após Token Exchange

## Diagnóstico Rápido (30 segundos)

```bash
# 1. Executar diagnóstico automático
docker-compose exec api python scripts/diagnose_401.py

# 2. Ver logs em tempo real
docker-compose logs -f api | grep -E "401|🚨"
```

## 5 Causas Mais Comuns (e Soluções)

### 1. 🔴 App sem Permissões no Portal
```bash
# Portal Conta Azul → Integrações → APIs → Seu App → Permissões
# ✅ Habilitar: Leitura de dados da empresa, financeiros, contas a receber
# Revogar autorizações antigas e refazer OAuth
```

### 2. 🟡 App em Sandbox (mas código usa Produção)
```bash
# Portal Conta Azul → Integrações → APIs → Seu App
# ✅ Migrar para PRODUÇÃO
# Ou verificar se está usando endpoints corretos
```

### 3. 🟠 Scopes Incorretos
```bash
# Verificar no código:
cat api/app/services_auth.py | grep "SCOPES ="
# Deve ser: openid profile aws.cognito.signin.user.admin

# Refazer fluxo OAuth se scopes mudaram
```

### 4. 🟢 URL da API Errada
```bash
cat .env | grep API_BASE_URL
# ✅ Correto: https://api.contaazul.com
# ❌ Errado: https://api.conta-azul.com (com hífen)
```

### 5. 🔵 Credenciais Erradas
```bash
cat .env | grep CONTA_AZUL_CLIENT
# Comparar com Portal Conta Azul
# Copiar novamente (sem espaços extras)
# docker-compose restart api
```

---

## Fluxo de Resolução

```
Erro 401 ao buscar /v1/me?
         ↓
1. Executar: diagnose_401.py
         ↓
2. Seguir instruções do script
         ↓
3. Corrigir problemas identificados
         ↓
4. Reiniciar: docker-compose restart api
         ↓
5. Refazer OAuth: GET /connect
         ↓
6. Verificar logs: logs -f api
         ↓
    ✅ Sucesso?
```

---

## Log de Sucesso vs Erro

### ✅ Sucesso
```
INFO - 📊 Status Code: 200
INFO - ✅ Informações da conta obtidas: id=a1b2c3d4...
INFO - ✅ Autenticação concluída com sucesso!
```

### ❌ Erro 401
```
ERROR - 🚨 ERRO 401 UNAUTHORIZED ao buscar /v1/me
ERROR - Error Type: insufficient_scope
ERROR - 💡 Possíveis causas:
ERROR -    1. App sem permissão de leitura no Portal
```

---

## Checklist Ultra-Rápido

Quando tiver 401, verificar NESTA ORDEM:

1. [ ] Portal: App em PRODUÇÃO?
2. [ ] Portal: Permissões de LEITURA habilitadas?
3. [ ] .env: URLs corretas? (api.contaazul.com)
4. [ ] .env: Credenciais corretas?
5. [ ] Código: Scopes corretos? (openid profile...)
6. [ ] Revogar autorizações antigas e refazer OAuth

---

## Comandos Úteis

```bash
# Ver configuração completa
cat .env | grep CONTA_AZUL

# Ver logs filtrados
docker-compose logs api | grep -A 20 "Etapa 2"

# Diagnóstico completo
docker-compose exec api python scripts/diagnose_401.py

# Reiniciar após mudanças
docker-compose restart api

# Testar endpoint diretamente
curl -i https://api.contaazul.com/v1/me \
  -H "Authorization: Bearer SEU_TOKEN"
```

---

## URLs Oficiais (para copiar/colar)

```bash
CONTA_AZUL_AUTH_URL=https://auth.contaazul.com/login
CONTA_AZUL_TOKEN_URL=https://auth.contaazul.com/oauth2/token
CONTA_AZUL_API_BASE_URL=https://api.contaazul.com
```

---

## Links Importantes

- **Portal:** https://portal.contaazul.com
- **Troubleshooting completo:** `TROUBLESHOOTING.md` (seção 2.A1)
- **Diagnóstico detalhado:** `DIAGNOSTICO_401.md`
- **Script diagnóstico:** `api/scripts/diagnose_401.py`

---

**Última atualização:** 2026-02-11

