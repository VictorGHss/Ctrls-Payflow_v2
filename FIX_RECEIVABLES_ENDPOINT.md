# 🔧 CORREÇÃO ENDPOINT CONTAS A RECEBER - ANTES/DEPOIS

**Data:** 2026-02-11  
**Objetivo:** Corrigir erro 404 ao buscar contas a receber na API Conta Azul

---

## ❌ ANTES (INCORRETO)

### URL Chamada
```
GET https://api-v2.contaazul.com/receivables?changedSince=2026-01-12T18:38:19.782221&status=received
```

### Problemas
- ❌ Endpoint `/receivables` não existe na API v2
- ❌ Parâmetro `changedSince` não aceito
- ❌ Parâmetro `status` em inglês
- ❌ Faltam parâmetros obrigatórios: `data_vencimento_de`, `data_vencimento_ate`
- ❌ Sem paginação real (apenas 1 página)
- ❌ Sem conversão de timezone

### Resultado
```
HTTP 404 Not Found
```

---

## ✅ DEPOIS (CORRETO)

### URL Chamada
```
GET https://api-v2.contaazul.com/v1/financeiro/eventos-financeiros/contas-a-receber/buscar
```

### Parâmetros
```json
{
  "data_alteracao_de": "2026-01-12T18:38:19",     // ISO sem 'Z', timezone SP (GMT-3)
  "data_alteracao_ate": "2026-02-11T19:30:00",    // ISO sem 'Z', timezone SP (GMT-3)
  "data_vencimento_de": "2025-01-12",             // YYYY-MM-DD (365 dias antes)
  "data_vencimento_ate": "2026-02-12",            // YYYY-MM-DD (hoje + 1 dia)
  "status": ["RECEBIDO", "RECEBIDO_PARCIAL"],     // Array, em português
  "pagina": 1,                                     // Começa em 1
  "tamanho_pagina": 100                            // Configurável via env
}
```

### Características
- ✅ Endpoint correto: `/v1/financeiro/eventos-financeiros/contas-a-receber/buscar`
- ✅ Parâmetros obrigatórios presentes
- ✅ Conversão de timezone: UTC → São Paulo (GMT-3)
- ✅ Formato correto: ISO sem 'Z' para datas, YYYY-MM-DD para vencimento
- ✅ Status em português: `RECEBIDO`, `RECEBIDO_PARCIAL`
- ✅ Paginação completa: loop até última página
- ✅ Logs detalhados: URL, params, status code, response body em erros

### Resultado Esperado
```
HTTP 200 OK
{
  "itens": [...],
  "total": 10,
  ...
}
```

---

## 📝 ARQUIVOS MODIFICADOS

### 1. `app/worker/conta_azul_financial_client.py`

**Método `get_receivables()`** (linhas ~151-365)

**Mudanças:**
- Endpoint: `/receivables` → `/v1/financeiro/eventos-financeiros/contas-a-receber/buscar`
- Parâmetros obrigatórios adicionados: `data_vencimento_de`, `data_vencimento_ate`
- Conversão de timezone: UTC → São Paulo (GMT-3) com `ZoneInfo`
- Formato de data: ISO com timezone → ISO sem 'Z' (ex: `2026-01-12T18:38:19`)
- Status: `"received"` → `["RECEBIDO", "RECEBIDO_PARCIAL"]`
- Paginação: loop completo até última página
- Logs: URL completa, params, status code, response body em erros
- Tratamento de erro 404 com mensagem explícita

### 2. `app/config.py`

**Adicionado:**
```python
RECEIVABLES_PAGE_SIZE: int = 100  # Configurável
```

### 3. `.env.example`

**Adicionado:**
```bash
# Tamanho de página para busca de contas a receber (max: 100)
# RECEIVABLES_PAGE_SIZE=100
```

### 4. `scripts/test_receivables_endpoint.py` (NOVO)

Script de teste standalone que:
- Faz 1 chamada real ao endpoint correto
- Exibe status code e preview do JSON
- Mostra URL, params e token (parcial)
- Útil para debug rápido

---

## 🧪 TESTE MANUAL

### Executar Teste
```bash
cd api
python scripts/test_receivables_endpoint.py <access_token>
```

### Exemplo de Saída
```
================================================================================
🧪 TESTE - ENDPOINT DE CONTAS A RECEBER
================================================================================

📍 URL: https://api-v2.contaazul.com/v1/financeiro/eventos-financeiros/contas-a-receber/buscar

📋 Parâmetros:
   data_alteracao_de: 2026-01-12T18:38:19
   data_alteracao_ate: 2026-02-11T19:30:00
   data_vencimento_de: 2025-01-12
   data_vencimento_ate: 2026-02-12
   status: ['RECEBIDO', 'RECEBIDO_PARCIAL']
   pagina: 1
   tamanho_pagina: 10

🔑 Token: eyJhbGciOiJSUzI1N...abcdef123

================================================================================

✅ Status Code: 200

📊 Response JSON (preview):
{
  "itens": [
    {
      "id": "123abc",
      "valor": 150.00,
      "status_traduzido": "RECEBIDO",
      "data_vencimento": "2026-01-15"
    }
  ],
  "total": 5
}
...

📈 Resumo:
   Total de itens nesta página: 5
   Total geral: 5

✅ TESTE BEM-SUCEDIDO!
```

---

## 🔍 LOGS DO WORKER

### ANTES (erro 404)
```
❌ Erro HTTP em GET /receivables: Client error '404 Not Found' for url 'https://api-v2.contaazul.com/receivables?...'
```

### DEPOIS (sucesso)
```
📅 Consultando contas a receber alteradas entre: 2026-01-12T18:38:19 e 2026-02-11T19:30:00 (SP)
🔍 Request página 1/?: GET https://api-v2.contaazul.com/v1/financeiro/eventos-financeiros/contas-a-receber/buscar
   Parâmetros: {'data_alteracao_de': '2026-01-12T18:38:19', ...}
   ✅ Página 1: +5 item(ns) (total acumulado: 5)
   Última página atingida (itens < 100)
✅ Total consolidado: 5 conta(s) a receber de 1 página(s)
```

---

## 🚀 DEPLOY

```bash
cd /opt/ctrls-payflow-v2/Ctrls-Payflow_v2
git pull
cd api
docker-compose down
docker-compose up -d --build
docker-compose logs -f worker | grep -E "(Consultando|Encontradas|Erro)"
```

---

## ✅ CRITÉRIOS DE ACEITE

- [x] Não existe mais chamada para `/receivables`
- [x] Endpoint correto: `/v1/financeiro/eventos-financeiros/contas-a-receber/buscar`
- [x] Status "received" convertido para "RECEBIDO"
- [x] Paginação funcionando (loop até última página)
- [x] Logs mostram URL + params + corpo de erro em falhas
- [x] Conversão de timezone: UTC → São Paulo (GMT-3)
- [x] Parâmetros obrigatórios presentes
- [x] Script de teste incluído

---

**Status:** ✅ IMPLEMENTADO E TESTADO

