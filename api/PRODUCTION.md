# Guia de Produção - PayFlow API

## 🚀 Deployment Production-Ready

### 1. Segurança

#### Variáveis de Ambiente

**NUNCA** commit `.env` ou secrets no Git:

```bash
# Usar secret management (ex: AWS Secrets Manager, Vault, etc)
# Local: arquivo .env (ignorado no .gitignore)
# Docker: passar via --env-file ou secrets

docker run --env-file /secure/.env.production ...
```

#### MASTER_KEY

```bash
# Gerar com 32 bytes
python scripts/generate_key.py

# Salvar em local seguro (not in Git):
# - AWS Secrets Manager
# - HashiCorp Vault
# - Google Secret Manager
# - Kubernetes Secrets (se usar K8s)

# No Docker Compose:
# Usar arquivo separado .env.production (não commitado)
```

#### HTTPS Obrigatório

```yaml
# docker-compose.yml com HTTPS via Cloudflare Tunnel
cloudflared:
  image: cloudflare/cloudflared:latest
  environment:
    TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
  restart: always
```

#### SMTP Seguro

```env
# Usar TLS (não SSL)
SMTP_USE_TLS=true
SMTP_PORT=587

# Ou SMTPS (com certificate verification)
SMTP_PORT=465
SMTP_USE_SMTPS=true

# Senhas: usar app passwords (não senhas principais)
# Gmail: myaccount.google.com/apppasswords
# Office365: criar app password
```

### 2. Database

#### Backup Regular

```bash
# Fazer backup de payflow.db
docker exec payflow-api sqlite3 /app/data/payflow.db ".backup /backup/payflow.db"

# Ou via volume:
docker cp payflow-api:/app/data/payflow.db /backup/payflow-$(date +%Y%m%d).db
```

#### Replicação (Futuro)

Para alta disponibilidade:
- Considerar migração para PostgreSQL
- Usar Alembic para migrações
- Implementar read replicas

#### Monitoramento

```bash
# Checar tamanho do banco
ls -lh data/payflow.db

# Verificar integridade
sqlite3 data/payflow.db "PRAGMA integrity_check;"

# Vacuum periodicamente
sqlite3 data/payflow.db "VACUUM;"
```

### 3. Performance

#### Rate Limiting Local

Conta Azul permite:
- 600 requisições/minuto
- 10 requisições/segundo

PayFlow implementa:
- Backoff exponencial em 429
- Pooling de conexões HTTP

Para distribuído (futuro): usar Redis para rate limit store.

#### Polling Interval

```env
# Ajuste baseado em volume:
POLLING_INTERVAL_SECONDS=300  # 5 min (default)
POLLING_INTERVAL_SECONDS=600  # 10 min (mais leve)
POLLING_INTERVAL_SECONDS=1800 # 30 min (muito leve)
```

Recomendação: **300-600 segundos** (5-10 min)

#### Database Queries

Índices criados automaticamente:
```sql
-- account_id indexado em:
CREATE INDEX idx_oauth_tokens_account_id ON oauth_tokens(account_id);
CREATE INDEX idx_polling_checkpoints_account_id ON polling_checkpoints(account_id);
CREATE INDEX idx_sent_receipts_account_id ON sent_receipts(account_id);
CREATE INDEX idx_azul_accounts_account_id ON azul_accounts(account_id);
```

### 4. Monitoramento & Logs

#### Health Checks

```bash
# K8s/Docker
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1
```

#### Logging

Integrar com ELK / Splunk / CloudWatch:

```python
# Em app/logging.py, adicionar handler remoto:
import logging.handlers

handler = logging.handlers.SysLogHandler(
    address=('logging.service.com', 514)
)
logger.addHandler(handler)
```

#### Métricas (Futuro)

```bash
# Adicionar Prometheus
pip install prometheus-client

# Métricas importantes:
# - payflow_emails_sent_total
# - payflow_emails_failed_total
# - payflow_polling_duration_seconds
# - payflow_database_connections
```

### 5. Docker Security

#### Build Seguro

```dockerfile
# ✅ Usar multi-stage (já implementado)
FROM python:3.10-slim as builder
FROM python:3.10-slim as runtime

# ✅ Usuário não-root (já implementado)
RUN useradd -m -u 1000 appuser
USER appuser

# ✅ Remover pacotes desnecessários
RUN apt-get remove -y gcc apt-utils

# ✅ Não usar latest tags
FROM python:3.10-slim  # versão fixa, não :latest
```

#### Container Security

```bash
# Escanear imagem por vulnerabilidades
docker scan payflow-api

# Usar private registry (não Docker Hub público)
docker tag payflow-api:1.0.0 myregistry.azurecr.io/payflow-api:1.0.0
docker push myregistry.azurecr.io/payflow-api:1.0.0

# Assinar imagem (Notary)
notary delegation enable myregistry.azurecr.io/payflow-api
```

### 6. Scaling

#### Horizontal (múltiplas instâncias)

```yaml
# docker-compose.yml com múltiplos workers
worker:
  deploy:
    replicas: 3  # 3 instâncias do worker

api:
  deploy:
    replicas: 2  # 2 instâncias da API
  ports:
    - "8000-8001:8000"
```

Ou Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payflow-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payflow-api
  template:
    ...
```

#### Load Balancing

```yaml
# docker-compose com proxy reverso
proxy:
  image: traefik:latest
  ports:
    - "443:443"
    - "80:80"
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  environment:
    - TRAEFIK_API_DASHBOARD=true
```

### 7. Disaster Recovery

#### Backup Automático

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/payflow"
DB_PATH="/app/data/payflow.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup local
docker cp payflow-api:$DB_PATH $BACKUP_DIR/payflow_$TIMESTAMP.db

# Backup remoto (S3, Azure Blob, etc)
aws s3 cp $BACKUP_DIR/payflow_$TIMESTAMP.db s3://my-bucket/backups/

# Manter apenas 7 dias
find $BACKUP_DIR -mtime +7 -delete
```

Agendar com cron:
```bash
0 2 * * * /scripts/backup.sh  # 2 AM diariamente
```

#### Restore

```bash
# Restaurar de backup
docker cp /backups/payflow_20250210.db payflow-api:/app/data/payflow.db
docker restart payflow-api
```

### 8. CI/CD

#### GitHub Actions (exemplo)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
      - run: ruff check app/

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: docker/build-push-action@v4
        with:
          push: true
          tags: myregistry.azurecr.io/payflow-api:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - run: docker-compose -f docker-compose.prod.yml up -d
```

### 9. Compliance & Auditoria

#### LGPD (Lei Geral de Proteção de Dados)

- ✅ Dados criptografados em repouso (MASTER_KEY)
- ✅ HTTPS em trânsito (Cloudflare Tunnel)
- ✅ Logs de acesso (email_logs, audit trail)
- ✅ Direito ao esquecimento (script para deletar dados)

```bash
# Script de LGPD: deletar dados de um usuário
python scripts/purge_user_data.py --account_id abc123
```

#### Auditoria

```sql
-- Auditar envios de email
SELECT account_id, doctor_email, status, created_at 
FROM email_logs 
ORDER BY created_at DESC 
LIMIT 100;

-- Auditar modificações de tokens
SELECT account_id, updated_at 
FROM oauth_tokens 
ORDER BY updated_at DESC;
```

### 10. Checklist Pré-Produção

- [ ] MASTER_KEY gerada e armazenada de forma segura
- [ ] .env.production criado (não commitado)
- [ ] SMTP testado e funcionando
- [ ] Conta Azul OAuth testada end-to-end
- [ ] Cloudflare Tunnel configurado (HTTPS)
- [ ] Testes passando (pytest -v)
- [ ] Linting passando (ruff check)
- [ ] Docker image buildada e testada
- [ ] Backup strategy definida
- [ ] Logging/monitoring configurado
- [ ] Escalabilidade planejada
- [ ] LGPD/compliance review done

### 11. Monitoramento Contínuo

```bash
# Ver status dos containers
docker ps -a

# Ver logs de erro
docker logs payflow-api | grep ERROR
docker logs payflow-worker | grep ERROR

# Verificar uso de recursos
docker stats payflow-api payflow-worker

# Health check
curl http://localhost:8000/healthz
curl http://localhost:8000/ready
```

### 12. Upgrade & Maintenance

#### Zero Downtime Deploy

```bash
# 1. Build nova versão
docker-compose build

# 2. Scale worker temporariamente
docker-compose up -d --scale worker=2

# 3. Deploy nova versão da API
docker-compose stop api
docker-compose up -d api

# 4. Verificar health
curl http://localhost:8000/ready

# 5. Reduzir workers
docker-compose up -d --scale worker=1
```

#### Database Migrations

```bash
# Alembic (quando implementar)
alembic upgrade head

# Rollback se necessário
alembic downgrade -1
```

---

**Versão**: 1.0.0  
**Status**: ✅ Production Ready  
**Last Updated**: 2025-02-10

