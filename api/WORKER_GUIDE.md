# 🚀 Worker - Polling de Contas a Receber

Serviço independente que executa periodicamente para consultar, processar e enviar recibos de contas a receber da Conta Azul.

## 📋 Componentes

### main.py
Loop principal do worker. Coordena o fluxo de polling de todas as contas ativas.

```python
python -m app.worker.main
```

### ContaAzulFinancialClient
Cliente HTTP para API Financeira da Conta Azul.

Funcionalidades:
- Consulta contas a receber (receivables)
- Busca detalhes de parcelas (installments)
- Obtém URLs de recibos
- Download de PDFs

Rate limiting:
- 10 req/s (local)
- 600 req/min (API)
- Backoff exponencial em 429

### ReceiptDownloader
Gerencia download e validação de recibos.

Validações:
- Verificação de magic bytes (%PDF)
- Tamanho (1KB - 100MB)
- Hash SHA256 para deduplicação

### FinancialProcessor
Orquestra o fluxo completo: checkpoint → consulta → validação → download → email.

## 🔄 Fluxo de Processamento

```
1. Worker Loop (a cada N segundos)
   ├─ Buscar contas ativas
   └─ Para cada conta:
      ├─ Obter token (renovar se expirado)
      ├─ Buscar checkpoint
      ├─ Consultar receivables desde último checkpoint
      └─ Para cada receivable:
         ├─ Buscar detalhes completos
         ├─ Para cada parcela:
         │  ├─ Validar status (received/paid)
         │  └─ Para cada anexo:
         │     ├─ Verificar idempotência
         │     ├─ Baixar PDF
         │     ├─ Validar PDF
         │     ├─ Resolver email médico
         │     ├─ Enviar email com anexo
         │     └─ Registrar envio
         └─ Atualizar checkpoint
```

## 🗂️ Tabelas de Banco

### FinancialCheckpoint
Armazena o último ponto de verificação por conta.

```sql
CREATE TABLE financial_checkpoints (
  id INTEGER PRIMARY KEY,
  account_id VARCHAR(255) UNIQUE NOT NULL,
  last_processed_changed_at DATETIME,
  checkpoint_updated_at DATETIME,
  metadata JSON
);
```

### SentReceipt
Registra recibos enviados (idempotência).

```sql
CREATE TABLE sent_receipts (
  id INTEGER PRIMARY KEY,
  account_id VARCHAR(255) NOT NULL,
  installment_id VARCHAR(255) NOT NULL,
  attachment_url TEXT NOT NULL,
  payment_id VARCHAR(255),
  doctor_email VARCHAR(255) NOT NULL,
  sent_at DATETIME NOT NULL,
  receipt_hash VARCHAR(64),
  metadata JSON,
  UNIQUE(account_id, installment_id, attachment_url)
);
```

### EmailLog
Log de tentativas de envio de email.

```sql
CREATE TABLE email_logs (
  id INTEGER PRIMARY KEY,
  account_id VARCHAR(255) NOT NULL,
  receipt_id VARCHAR(255) NOT NULL,
  doctor_email VARCHAR(255) NOT NULL,
  status VARCHAR(50) NOT NULL,  -- 'sent', 'failed'
  error_message TEXT,
  created_at DATETIME,
  updated_at DATETIME
);
```

## 🔐 Segurança

### Sem Logging de PDFs
- PDFs são baixados em memória
- Nunca salvos em disco (sem PII)
- Apenas enviados por email
- Garbage collected após envio

### Sem PII Desnecessária
- Não loga conteúdo de emails
- Não loga PDFs
- Apenas logs estruturados de eventos

### Idempotência Forte
- Unique constraint: (installment_id, attachment_url)
- Hash SHA256 do PDF para deduplicação
- Verificação antes de processar

### Checkpoint Resiliente
- Janela de segurança: volta N minutos
- Evita perda de eventos
- Atualizado após processamento bem-sucedido

## 📊 Rate Limiting

### Local (10 req/s)
```python
MIN_INTERVAL_BETWEEN_REQUESTS = 0.1  # 100ms
```

### API Conta Azul (600 req/min, ~10 req/s)
- Respeita headers X-RateLimit
- Backoff exponencial em 429
- Máximo 5 tentativas (1s, 2s, 4s, 8s, 16s)

## 📝 Configuração

```env
# Polling
POLLING_INTERVAL_SECONDS=300         # 5 minutos
POLLING_SAFETY_WINDOW_MINUTES=10     # Volta 10 min
POLLING_INITIAL_LOOKBACK_DAYS=30     # Inicial: 30 dias

# Fallback de emails
DOCTORS_FALLBACK_JSON={"Cliente1": "doctor1@example.com", ...}
```

## 🧪 Testes

### Testes Unitários

```bash
# Todos os testes
pytest tests/test_worker.py -v

# Teste específico
pytest tests/test_worker.py::test_is_receipt_already_sent -v

# Com coverage
pytest tests/test_worker.py -v --cov=app.worker
```

### Testes Inclusos

**Checkpoint:**
- Criação de novo checkpoint
- Reutilização de existente
- Atualização
- Cálculo de data com janela de segurança
- Padrão (30 dias atrás)

**Idempotência:**
- Detecção de recibo não enviado
- Detecção de recibo já enviado
- Constraint de unicidade
- URLs diferentes para mesma parcela
- Metadata e hash armazenados

**Integração:**
- Busca de contas ativas
- Filtragem de inativas

## 🚀 Rodar Localmente

### Terminal 1: API
```bash
uvicorn app.main:app --reload
```

### Terminal 2: Worker
```bash
python -m app.worker.main
```

Esperado:
```
INFO:     Worker iniciado
INFO:     Intervalo de polling: 300s
INFO:     Janela de segurança: 10min
INFO:     Processando 1 conta(s) ativa(s)
DEBUG:   Consultando receivables desde 2026-02-10T10:20:00Z...
INFO:     Ciclo completo: 5 recibos, 0 erro(s)
```

## 🐳 Docker

### docker-compose.yml

```yaml
services:
  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  worker:
    build: .
    command: python -m app.worker.main
```

Rodar:
```bash
docker-compose up
```

## 📈 Monitoramento

### Logs Estruturados
```
INFO: Processando 1 conta(s) ativa(s)
DEBUG: Consultando receivables desde ...
DEBUG: Encontrados 5 item(ns)
INFO: ✓ Recibo enviado com sucesso para doctor@example.com
INFO: Ciclo completo: 5 recibos, 0 erro(s)
```

### Métricas (Recomendado adicionar)
- Recibos processados/ciclo
- Tempo de ciclo
- Taxa de erro
- Taxa de retry (429)

### Banco de Dados
```bash
# Ver checkpoints
sqlite3 data/payflow.db "SELECT * FROM financial_checkpoints;"

# Ver recibos enviados
sqlite3 data/payflow.db "SELECT COUNT(*) FROM sent_receipts WHERE status='sent';"

# Ver emails falhados
sqlite3 data/payflow.db "SELECT * FROM email_logs WHERE status='failed';"
```

## 🔧 Troubleshooting

### Erro: "Token não encontrado"
- Verificar que conta foi conectada via OAuth (/connect)
- Verificar que token não expirou

### Erro: "Rate limit 429"
- Backoff exponencial está ativo
- Máximo 5 tentativas
- Verifique headers X-RateLimit na API

### Nenhum recibo processado
- Verificar que há contas ativas (`is_active=1`)
- Verificar que há receivables com `status='received'`
- Verificar logs do worker

### Email não enviado
- Verificar SMTP_* em .env
- Verificar que doctor_email foi resolvido
- Verificar logs de erro

## 📚 Próximos Passos

- [ ] Adicionar métricas Prometheus
- [ ] Webhook listener (quando Conta Azul suportar)
- [ ] Retry automático de emails falhados
- [ ] Dashboard de status do worker
- [ ] Alertas (Slack, email, etc)

---

**Status**: ✅ Production Ready

Desenvolvido com segurança, idempotência e observabilidade.

