# 🚀 Deploy - PayFlow API

Guia completo de deploy em produção com Docker, Cloudflare Tunnel e Access (Google SSO).

## 📋 Pré-requisitos

### Servidor (Home Server / VPS / Cloud)
- Docker instalado (`docker --version`)
- Docker Compose instalado (`docker-compose --version`)
- Git
- Acesso SSH

### Cloudflare
- Conta ativa
- Domínio registrado e apontando para Cloudflare
- (Opcional) Zero Trust habilitado

---

## 🔧 Passo 1: Preparar Servidor

```bash
# SSH no servidor
ssh user@seu-servidor.com

# Instalar Docker (se necessário)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verificar
docker --version
docker-compose --version
```

---

## 📦 Passo 2: Clonar Repositório

```bash
# No servidor
cd ~
git clone https://github.com/seu-usuario/payflow.git
cd payflow/api
```

---

## 🔐 Passo 3: Configurar .env

```bash
# Copiar exemplo
cp .env.example .env

# Editar
nano .env  # ou vim, vi, etc
```

### .env Produção

```env
# === Conta Azul ===
CONTA_AZUL_CLIENT_ID=seu_client_id_producao
CONTA_AZUL_CLIENT_SECRET=seu_client_secret_producao
CONTA_AZUL_REDIRECT_URI=https://payflow.seu-dominio.com/oauth/callback

# === Segurança ===
# Gerar com: python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
MASTER_KEY=gerar_chave_de_32_bytes_base64_encoded
JWT_SECRET=gerar_secret_aleatorio_seguro

# === SMTP (Produção) ===
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.sua_api_key_producao
SMTP_FROM=noreply@seu-dominio.com
SMTP_REPLY_TO=suporte@seu-dominio.com
SMTP_USE_TLS=true
SMTP_TIMEOUT=10

# === Database ===
DATABASE_URL=sqlite:///./data/payflow.db

# === Polling ===
POLLING_INTERVAL_SECONDS=300
POLLING_SAFETY_WINDOW_MINUTES=10

# === Cloudflare Tunnel ===
# Será preenchido no Passo 4
CLOUDFLARE_TUNNEL_TOKEN=

# === Fallback de Emails (Opcional) ===
DOCTORS_FALLBACK_JSON={"Dr. João": "joao@clinica.com"}

# === Ambiente ===
ENVIRONMENT=production
LOG_LEVEL=INFO
```

**Salvar**: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## ☁️ Passo 4: Configurar Cloudflare Tunnel

### 4.1 Acessar Cloudflare Dashboard

1. Ir para https://dash.cloudflare.com
2. Selecionar seu domínio
3. Menu lateral: **Zero Trust**
4. **Networks → Tunnels**

### 4.2 Criar Tunnel

```
Tunnels → Create a tunnel
├─ Tunnel name: payflow-api
├─ Connector: Docker
└─ Next
```

### 4.3 Copiar Token

Você verá um comando como:

```bash
docker run cloudflare/cloudflared:latest tunnel --no-autoupdate run --token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Copiar apenas o token** (parte após `--token`):

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhIjoiMTIzNDU2Nzg5MCIsInQiOiJhYmNkZWZnaCIsInMiOiJodHRwczovL...
```

### 4.4 Salvar Token no .env

```bash
nano .env
```

Adicionar linha:
```env
CLOUDFLARE_TUNNEL_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 4.5 Configurar Public Hostname

Voltar ao Cloudflare Dashboard, aba **Public Hostnames**:

```
Public Hostnames → Add a public hostname
├─ Subdomain: payflow
├─ Domain: seu-dominio.com
├─ Type: HTTP
├─ URL: api:8000  ← IMPORTANTE: nome do container Docker
└─ Save hostname
```

**Resultado**: `https://payflow.seu-dominio.com` → `http://api:8000` (interno)

---

## 🔐 Passo 5: Proteger com Cloudflare Access (Google SSO)

### 5.1 Criar Aplicação

```
Zero Trust → Access → Applications
├─ Add an application
├─ Self-hosted
```

### 5.2 Configurar

```
Application Configuration:
├─ Application name: PayFlow API
├─ Session Duration: 24 hours
├─ Application domain: payflow.seu-dominio.com
└─ Next
```

### 5.3 Adicionar Login Provider

```
Identity providers:
├─ Add a login method
├─ Select: Google
├─ Seguir instruções para obter Client ID/Secret do Google
└─ Save
```

### 5.4 Criar Policy

```
Add a policy:
├─ Policy name: Require Google Account
├─ Action: Allow
├─ Configure rules:
│  ├─ Include:
│  │  └─ Selector: Emails
│  │     Value: seu_email@gmail.com, admin@seu-dominio.com
│  └─ Exclude: (vazio)
└─ Next → Add application
```

**Resultado**: Apenas emails autorizados podem acessar `https://payflow.seu-dominio.com`

---

## 🐳 Passo 6: Build e Deploy Docker

```bash
# Verificar que .env está completo
cat .env | grep -E "MASTER_KEY|CLOUDFLARE_TUNNEL_TOKEN|SMTP"

# Build das imagens
docker-compose build --no-cache

# Iniciar serviços
docker-compose up -d

# Verificar status
docker-compose ps
```

**Output esperado**:
```
NAME                STATUS              PORTS
payflow-api         Up (healthy)        
payflow-worker      Up                  
payflow-cloudflared Up                  
```

---

## ✅ Passo 7: Validar Deploy

### 7.1 Verificar Logs

```bash
# API
docker-compose logs -f api

# Esperado:
# INFO: Uvicorn running on http://0.0.0.0:8000
# INFO: PayFlow API iniciada - 1.0.0

# Worker
docker-compose logs -f worker

# Esperado:
# Worker iniciado
# Intervalo de polling: 300s

# Cloudflared
docker-compose logs -f cloudflared

# Esperado:
# Registered tunnel connection
```

### 7.2 Testar Localmente

```bash
# Dentro do servidor
curl http://localhost:8000/healthz

# Esperado:
{"status":"ok"}
```

### 7.3 Testar via Cloudflare Tunnel

```bash
# De qualquer lugar (browser ou curl)
curl https://payflow.seu-dominio.com/healthz

# Se Cloudflare Access estiver ativo, você será redirecionado para login Google
# Após autenticar: {"status":"ok"}
```

### 7.4 Testar Swagger UI

Abrir browser:
```
https://payflow.seu-dominio.com/docs
```

1. Será redirecionado para Google login
2. Autenticar com conta autorizada
3. Verá Swagger UI

---

## 🔄 Passo 8: Iniciar OAuth com Conta Azul

### ⚠️ Importante: OAuth com Cloudflare Tunnel

**O OAuth NÃO funciona com localhost!** É necessário usar domínio externo via Cloudflare Tunnel.

**URLs corretas (validadas):**
```
Authorize: https://auth.contaazul.com/login
Token: https://auth.contaazul.com/oauth2/token
Redirect URI: https://payflow.seu-dominio.com/oauth/callback
Scope: openid profile aws.cognito.signin.user.admin
```

### 8.1 Acessar Endpoint /connect

```
Browser: https://payflow.seu-dominio.com/connect
```

Será redirecionado para:
1. **Cloudflare Access** → Login Google (se configurado)
2. **Conta Azul** → Login + Autorizar

### 8.2 Autorizar Aplicação

Na tela do Conta Azul:
- Fazer login com credenciais da empresa
- Clicar em **Autorizar**
- Será redirecionado de volta para `/oauth/callback`

### 8.3 Verificar Tokens Salvos

```bash
# No servidor
docker-compose exec api bash

# Dentro do container
sqlite3 data/payflow.db
sqlite> SELECT account_id, created_at FROM oauth_tokens;
# Deve listar seu account_id

sqlite> .quit
exit
```

---

## 🛠️ Manutenção

### Ver Logs em Tempo Real

```bash
docker-compose logs -f api worker
```

### Reiniciar Serviços

```bash
# Reiniciar tudo
docker-compose restart

# Reiniciar apenas API
docker-compose restart api

# Reiniciar apenas Worker
docker-compose restart worker
```

### Parar Serviços

```bash
docker-compose down
```

### Atualizar Código

```bash
# Parar
docker-compose down

# Puxar atualizações
git pull origin main

# Rebuild e reiniciar
docker-compose build --no-cache
docker-compose up -d

# Verificar
docker-compose logs -f api
```

### Backup do Banco de Dados

```bash
# Criar backup
cp data/payflow.db data/payflow.db.backup.$(date +%Y%m%d_%H%M%S)

# Listar backups
ls -lh data/*.backup.*
```

### Restaurar Backup

```bash
# Parar serviços
docker-compose down

# Restaurar
cp data/payflow.db.backup.20260210_143000 data/payflow.db

# Reiniciar
docker-compose up -d
```

---

## 🔐 Atualizar MASTER_KEY (Rotação de Chave)

### Quando fazer
- Anualmente (best practice)
- Após suspeita de comprometimento
- Como parte de auditoria de segurança

### Procedimento

```bash
# 1. Gerar nova chave
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
# Salvar output como: NEW_MASTER_KEY

# 2. Backup do banco
cp data/payflow.db data/payflow.db.backup.$(date +%Y%m%d_%H%M%S)

# 3. Editar .env
nano .env

# Adicionar linha:
# OLD_MASTER_KEYS=<chave_antiga>
# Atualizar:
# MASTER_KEY=<NEW_MASTER_KEY>

# 4. Rebuild e reiniciar
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 5. Verificar logs
docker-compose logs api | grep -i "crypto\|error"

# 6. Após 24h, remover OLD_MASTER_KEYS do .env
```

**Veja**: [SECURITY.md](SECURITY.md) para detalhes sobre rotação de chaves.

---

## 📊 Monitoramento

### Health Checks

```bash
# Localmente
curl http://localhost:8000/healthz
curl http://localhost:8000/ready

# Via Cloudflare
curl https://payflow.seu-dominio.com/healthz
```

### Logs Estruturados

```bash
# Ver logs com filtro
docker-compose logs api | grep ERROR
docker-compose logs worker | grep "processados\|erros"

# Ver apenas últimas 100 linhas
docker-compose logs --tail=100 api
```

### Métricas (Sugestão)

Para produção, considere adicionar:

**Prometheus + Grafana**:
```yaml
# Adicionar ao docker-compose.yml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
```

**Sentry (Error Tracking)**:
```env
# .env
SENTRY_DSN=https://...@sentry.io/...
```

```python
# app/main.py
import sentry_sdk
sentry_sdk.init(dsn=settings.SENTRY_DSN)
```

---

## 🚨 Troubleshooting

### Container não inicia

```bash
# Ver logs de erro
docker-compose logs api

# Verificar .env
cat .env | grep -E "MASTER_KEY|DATABASE_URL"

# Rebuild forçado
docker-compose down
docker-compose build --no-cache --pull
docker-compose up -d
```

### Cloudflare Tunnel não conecta

```bash
# Verificar logs do cloudflared
docker-compose logs cloudflared

# Erros comuns:
# - Token inválido → regenerar na Cloudflare
# - Firewall bloqueando → liberar portas 80, 443, 7844
# - DNS não propagado → aguardar alguns minutos
```

### OAuth falha (401 Unauthorized)

```bash
# Verificar credenciais no .env
cat .env | grep CONTA_AZUL

# Verificar que REDIRECT_URI no .env == Redirect URI no Portal Conta Azul
# Exemplo: https://payflow.seu-dominio.com/oauth/callback
```

### SMTP falha (535 Authentication Error)

```bash
# Gmail: verificar que App Password está correto
# SendGrid: verificar API key
# Testar SMTP:
docker-compose exec api python3 -c "
from app.services.mailer import MailerService
mailer = MailerService()
result = mailer.send_test_email('seu_email@gmail.com')
print(f'Resultado: {result}')
"
```

### Worker não processa contas

```bash
# Ver logs
docker-compose logs worker | grep -i "conta\|erro"

# Verificar se há contas ativas
docker-compose exec api bash
sqlite3 data/payflow.db
sqlite> SELECT account_id, is_active FROM azul_accounts;

# Se nenhuma conta: fazer OAuth primeiro
# Browser: https://payflow.seu-dominio.com/connect
```

**Mais soluções**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## 🔧 Configurações Avançadas

### Customizar Intervalo de Polling

```env
# .env
POLLING_INTERVAL_SECONDS=600  # 10 minutos
POLLING_SAFETY_WINDOW_MINUTES=15
```

```bash
docker-compose restart worker
```

### Habilitar Debug Logs

```env
# .env
LOG_LEVEL=DEBUG
```

```bash
docker-compose restart
```

### Limitar Recursos Docker

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
```

### Auto-restart em Falha

```yaml
# docker-compose.yml (já configurado)
services:
  api:
    restart: unless-stopped
  worker:
    restart: unless-stopped
```

---

## 📝 Checklist Pós-Deploy

- [ ] Cloudflare Tunnel conectado e ativo
- [ ] Cloudflare Access protegendo aplicação
- [ ] Health checks respondendo (200 OK)
- [ ] OAuth com Conta Azul funcionando
- [ ] Worker processando contas (ver logs)
- [ ] SMTP enviando emails (testar com send_test_email)
- [ ] Logs não mostram senhas/tokens em plaintext
- [ ] Backup do banco configurado
- [ ] Monitoramento ativo (opcional)

---

## 🆘 Suporte

Problemas ou dúvidas:
1. Consultar [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Ver logs: `docker-compose logs -f`
3. Abrir issue no GitHub
4. Contatar equipe de desenvolvimento

---

**Última atualização**: 2026-02-10

