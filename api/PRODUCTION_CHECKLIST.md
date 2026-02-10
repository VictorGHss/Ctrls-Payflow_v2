# ✅ PRODUCTION READINESS CHECKLIST

Checklist final antes de deploy em produção.

---

## 🔒 SEGURANÇA (CRÍTICO)

### Autenticação & Autorização
- [ ] OAuth2 Authorization Code implementado
- [ ] Tokens criptografados em repouso (MASTER_KEY 32 bytes)
- [ ] JWT tokens com expiração
- [ ] Refresh token rotation implementada
- [ ] Cloudflare Access com Google SSO configurado
- [ ] HTTPS obrigatório via Cloudflare Tunnel

### API Security
- [ ] CORS restritivo (apenas Conta Azul + seu domínio)
- [ ] TrustedHost middleware configurado
- [ ] Rate limiting implementado (10 req/s, 600 req/min)
- [ ] CSRF protection habilitada (se aplicável)
- [ ] Input validation em todos os endpoints
- [ ] SQL injection prevention (SQLAlchemy ORM)
- [ ] Command injection prevention
- [ ] XXE prevention (não parsear XML externo)

### Dados Sensíveis
- [ ] Logs nunca contêm tokens/passwords/PII (SensitiveDataFilter)
- [ ] Endpoints /docs e /redoc protegidos por Access
- [ ] .env não versionado (.gitignore)
- [ ] Secrets em manager seguro (não filesystem)
- [ ] Backup de banco criptografado
- [ ] Senhas SMTP e API keys seguras

### Network Security
- [ ] SSRF prevention implementada (validação de domínio)
- [ ] Apenas HTTPS permitido (no download de anexos)
- [ ] IPs privados/loopback bloqueados
- [ ] Redirects bloqueados (follow_redirects=False)
- [ ] Timeouts configurados (10-30s)
- [ ] Connection limits implementados
- [ ] DDoS protection via Cloudflare

### Docker/Container Security
- [ ] Imagem rodando como non-root (appuser)
- [ ] Dockerfile multi-stage
- [ ] .dockerignore otimizado
- [ ] Permissões restritas em /app/data (chmod 700)
- [ ] Volumes com permissões corretas
- [ ] Secrets via environment (não hardcoded)

---

## 🧪 TESTES (CRÍTICO)

### Testes Unitários
- [ ] pytest configurado e rodando
- [ ] Coverage > 80% (principais módulos)
- [ ] Testes de SSRF (test_security_ssrf.py)
- [ ] Testes de criptografia (test_oauth.py)
- [ ] Testes de idempotência (test_worker.py)
- [ ] Testes de email (test_mailer.py)
- [ ] Testes de rate limiting
- [ ] Testes de timeout

### Testes de Segurança
- [ ] SSRF validation tests passando
- [ ] Localhost/private IPs rejeitados
- [ ] AWS metadata endpoints bloqueados
- [ ] Invalid domains rejeitados
- [ ] Valid domains aceitos
- [ ] Redirects bloqueados (follow_redirects=False)

### Testes de Integração
- [ ] API + Worker comunicando
- [ ] Database queries funcionando
- [ ] Email SMTP mockado
- [ ] Cloudflare Tunnel conectando

### Testes de Carga
- [ ] Rate limiting em 10 req/s
- [ ] Worker não falling behind
- [ ] Database não slowdown
- [ ] Memory leaks testados

---

## 📦 DEPENDÊNCIAS (CRÍTICO)

### Requirements
- [ ] requirements.txt com versões pinadas (ex: fastapi==0.104.1)
- [ ] Todas as dependências têm hashes (pip-tools)
- [ ] Sem dependências desconhecidas
- [ ] CVE check realizado (pip-audit, safety)
- [ ] Dependências atualizadas (não obsoletas)

### Audit de Vulnerabilidades
```bash
pip install pip-audit safety
pip-audit
safety check
```

- [ ] Nenhuma vulnerabilidade HIGH/CRITICAL
- [ ] Vulnerabilidades MEDIUM investigadas
- [ ] Vulnerabilidades LOW documentadas

---

## 🔧 CONFIGURAÇÃO (CRÍTICO)

### Environment Variables
- [ ] CONTA_AZUL_CLIENT_ID definido
- [ ] CONTA_AZUL_CLIENT_SECRET definido
- [ ] CONTA_AZUL_REDIRECT_URI correto
- [ ] MASTER_KEY seguro (32 bytes)
- [ ] JWT_SECRET seguro
- [ ] SMTP_HOST/PORT/USER/PASSWORD corretos
- [ ] SMTP_FROM válido
- [ ] DATABASE_URL correto
- [ ] CLOUDFLARE_TUNNEL_TOKEN definido
- [ ] Todos em .env (não em código)
- [ ] .env não versionado

### Config Validation
- [ ] Todas as variáveis obrigatórias presentes
- [ ] Nenhum default inseguro
- [ ] Pydantic validation funcionando
- [ ] Error messages claras para config inválida

### Secrets Management
- [ ] Usar Secret Manager (AWS, Azure, Vault, 1Password)
- [ ] Não usar filesystem direto
- [ ] Rotação automática de secrets (se suportado)
- [ ] Auditoria de acesso a secrets

---

## 📊 DATABASE (CRÍTICO)

### SQLite
- [ ] data/payflow.db persistente (volume)
- [ ] Permissões restritas (chmod 700)
- [ ] Backup diário automático
- [ ] Teste de restore funciona
- [ ] Integridade do banco verificada

### Migrations
- [ ] Alembic migrations aplicadas
- [ ] Schema match code (ORM)
- [ ] Rollback tested
- [ ] Versionamento de schema

### Data Integrity
- [ ] Unique constraints implementados
- [ ] Foreign keys configuradas
- [ ] NOT NULL constraints
- [ ] Índices em colunas frecuentes

---

## 🚀 DEPLOYMENT (CRÍTICO)

### Docker Compose
- [ ] docker-compose.yml validado
- [ ] Volumes mapeados corretamente
- [ ] Networks configuradas
- [ ] Healthchecks funcionando
- [ ] Restart policies definidas
- [ ] Logging configurado

### Imagens Docker
- [ ] Build sem erros
- [ ] Imagem final < 500MB
- [ ] Base image atualizada
- [ ] Sem vulnerabilidades conhecidas

### Cloudflare Tunnel
- [ ] Tunnel criado e ativo
- [ ] CLOUDFLARE_TUNNEL_TOKEN definido
- [ ] Public hostname configurado
- [ ] --no-autoupdate flag ativo
- [ ] Healthcheck passando

### Cloudflare Access
- [ ] Application criada
- [ ] Google SSO configurado
- [ ] Emails autorizados definidos
- [ ] Policy testada (login funciona)
- [ ] MFA opcional configurado

---

## 📈 MONITORAMENTO (RECOMENDADO)

### Logging
- [ ] Logs centralizados (CloudWatch, Datadog, ELK)
- [ ] Rotation de logs configurado
- [ ] Severidade apropriada (INFO, WARNING, ERROR)
- [ ] PII não logged
- [ ] Timestamps em UTC

### Alertas
- [ ] Alert para erros 5xx
- [ ] Alert para rate limit hits
- [ ] Alert para failed auth
- [ ] Alert para database errors
- [ ] Alert para worker failures
- [ ] Slack/email notifications configuradas

### Métricas
- [ ] Requisições por segundo
- [ ] Latência API (p50, p95, p99)
- [ ] Taxa de erro
- [ ] Uso de CPU/Memory
- [ ] Uso de disco (data volume)
- [ ] Taxa de worker processing

### Health Checks
- [ ] GET /healthz respondendo
- [ ] Cloudflare Tunnel status
- [ ] Worker loop rodando
- [ ] Database conectando
- [ ] Email SMTP ping

---

## 🔄 OPERAÇÕES (RECOMENDADO)

### Backup & Disaster Recovery
- [ ] Backup diário do SQLite
- [ ] Retenção: 30 dias mínimo
- [ ] Teste de restore: semanal
- [ ] Backup remoto: sim
- [ ] Criptografia de backup: sim
- [ ] RTO definido: X horas
- [ ] RPO definido: Y minutos

### Key Management
- [ ] MASTER_KEY rotation planned (anual)
- [ ] Procedimento documentado (KEY_ROTATION.md)
- [ ] Teste de rotação feito
- [ ] OLD_MASTER_KEYS removido após rotação

### Rollback Plan
- [ ] Versionamento de código
- [ ] Container image tags
- [ ] Database migration rollback
- [ ] Procedure testada

### Scaling
- [ ] Worker escalável (se necessário)
- [ ] API pode escalar horizontalmente
- [ ] Database bottleneck identificado
- [ ] Load balancing (se aplicável)

---

## 📝 DOCUMENTAÇÃO (RECOMENDADO)

### README & Guides
- [ ] README.md completo
- [ ] DEPLOY.md com passo-a-passo
- [ ] SECURITY_AUDIT.md com riscos
- [ ] KEY_ROTATION.md com procedimento
- [ ] DOCKER_REFERENCE.md com comandos

### Runbooks
- [ ] Incident response
- [ ] Database recovery
- [ ] Key rotation
- [ ] Deployment
- [ ] Rollback

### Architecture
- [ ] Diagram da arquitetura
- [ ] Data flow diagram
- [ ] Security boundaries
- [ ] Network diagram

---

## 🔍 REVISÃO FINAL (ANTES DE GO-LIVE)

### Code Review
- [ ] Todos os PRs revisados
- [ ] Sem TODO/FIXME em código crítico
- [ ] Sem dead code
- [ ] Sem debug prints

### Security Review
- [ ] Penetration testing (opcional)
- [ ] Security audit completo
- [ ] OWASP Top 10 checked
- [ ] Risk assessment documento

### Performance Review
- [ ] Load testing realizado
- [ ] Latência aceitável
- [ ] CPU/Memory OK
- [ ] Disk space OK

### Compliance
- [ ] LGPD compliance (se aplicável)
- [ ] GDPR compliance (se aplicável)
- [ ] Data retention policies
- [ ] Privacy policy atualizada

---

## 📋 DIA DO DEPLOY

### Pre-deployment
- [ ] Backup atual do banco
- [ ] Status page criada
- [ ] Incident response team notificado
- [ ] Rollback plan revisado

### Deployment
```bash
# 1. Parar containers
docker-compose down

# 2. Fazer backup
cp data/payflow.db data/payflow.db.backup.$(date +%Y%m%d_%H%M%S)

# 3. Pull latest code
git pull

# 4. Build
docker-compose build

# 5. Run
docker-compose up -d

# 6. Verificar logs
docker-compose logs --tail=50

# 7. Teste manual
curl https://payflow.seu-dominio.com/healthz

# 8. Acessar aplicação
https://payflow.seu-dominio.com
```

- [ ] Deployment concluído sem erros
- [ ] Healthchecks passando
- [ ] Logs sem erros críticos
- [ ] Aplicação respondendo corretamente

### Post-deployment
- [ ] Monitorar logs por 1h
- [ ] Verificar métricas
- [ ] Testar fluxo OAuth
- [ ] Testar envio de email
- [ ] Comunicar ao time

---

## ✅ SIGN-OFF

| Role | Nome | Data | Assinatura |
|------|------|------|-----------|
| Dev Lead | | | |
| Security | | | |
| DevOps | | | |
| Product | | | |

---

**Status**: Ready for Production ✅

**Deploy Date**: 2026-02-10  
**Version**: 1.0.0  
**Environment**: Production

