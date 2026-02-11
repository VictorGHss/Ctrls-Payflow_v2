# 🔧 Fix: Erro 400 - tamanho_pagina inválido

**Data:** 2026-02-11  
**Erro:** HTTP 400 no smoke test OAuth  

---

## 🐛 Problema

Durante o fluxo OAuth, ao fazer smoke test do access_token no endpoint `/v1/pessoas`, a API retorna:

```json
{
  "error": "O tamanho da página deve ser um dos seguintes valores: 10, 20, 50, 100, 200, 500 ou 1000"
}
```

**Log**:
```
📊 Smoke Test Status Code: 400
❌ Erro ao buscar informações da conta: 400
```

---

## ✅ Solução

A API da Conta Azul v2 é **rigorosa** quanto aos valores de paginação permitidos.

**ANTES** (incorreto):
```python
API_URL = "https://api-v2.contaazul.com/v1/pessoas?pagina=1&tamanho_pagina=1"
```

**DEPOIS** (correto):
```python
API_URL = "https://api-v2.contaazul.com/v1/pessoas?pagina=1&tamanho_pagina=10"
```

### Valores Permitidos para `tamanho_pagina`

- ✅ **10** (menor valor, recomendado para smoke test)
- ✅ 20
- ✅ 50
- ✅ 100
- ✅ 200
- ✅ 500
- ✅ 1000
- ❌ 1 (INVÁLIDO)
- ❌ Qualquer outro valor (INVÁLIDO)

---

## 📝 Arquivos Corrigidos

1. **`api/app/services_auth.py`**
   ```python
   API_URL = "https://api-v2.contaazul.com/v1/pessoas?pagina=1&tamanho_pagina=10"
   ```

2. **`api/scripts/contaazul_smoke_test.py`**
   ```python
   SMOKE_TEST_URL = "https://api-v2.contaazul.com/v1/pessoas?pagina=1&tamanho_pagina=10"
   ```

3. **`README.md`**
   - Documentação atualizada com valores permitidos

---

## 🚀 Aplicar Correção

### No servidor

```bash
# 1. Navegar para o repositório
cd /opt/ctrls-payflow-v2/Ctrls-Payflow_v2

# 2. Pull das alterações
git pull

# 3. Rebuild container
cd api
docker-compose down
docker-compose up -d --build

# 4. Verificar logs
docker-compose logs -f api | grep -E "(Smoke Test|Status Code)"
```

---

## ✅ Resultado Esperado

Após a correção, os logs devem mostrar:

```
🔍 Validando token com smoke test na API
📊 Smoke Test Status Code: 200 ✅
✅ Token validado com sucesso - API respondeu 200
✅ id_token decodificado com sucesso
✅ Autenticação concluída com sucesso!
```

---

## 📊 Antes vs Depois

| Antes | Depois |
|-------|--------|
| `tamanho_pagina=1` | `tamanho_pagina=10` |
| HTTP 400 ❌ | HTTP 200 ✅ |
| OAuth falha | OAuth sucesso |

---

## 🔍 Como Detectar Este Erro

**Sintomas**:
- OAuth callback retorna HTTP 500
- Log mostra: `Smoke Test Status Code: 400`
- Mensagem: `"O tamanho da página deve ser um dos seguintes valores..."`

**Diagnóstico**:
```bash
# Verificar endpoint configurado
grep "API_URL" api/app/services_auth.py

# Deve mostrar:
# API_URL = "https://api-v2.contaazul.com/v1/pessoas?pagina=1&tamanho_pagina=10"
```

---

## 💡 Lição Aprendida

A API da Conta Azul v2 tem validações estritas de parâmetros. Sempre consultar a documentação oficial para valores permitidos em cada endpoint.

**Documentação**: https://developers.contaazul.com

---

**Status:** ✅ CORRIGIDO  
**Commit:** `fix: Corrige tamanho_pagina no endpoint /v1/pessoas`

