# 🔧 Troubleshooting - PayFlow API

Guia de solução de problemas comuns.

---

## 📋 Diagnóstico Rápido

### Verificar Status dos Serviços

```bash
# Status dos containers
docker-compose ps

# Esperado:
# payflow-api         Up (healthy)
# payflow-worker      Up
# payflow-cloudflared Up
```

### Verificar Logs

```bash
# Todos os logs
docker-compose logs -f

# Apenas API
docker-compose logs -f api

# Apenas Worker
docker-compose logs -f worker

# Filtrar erros
docker-compose logs api | grep ERROR
```

### Health Checks

```bash
# Local
curl http://localhost:8000/healthz
# Esperado: {"status":"ok"}

# Via Cloudflare
curl https://payflow.seu-dominio.com/healthz
```

---

## 🚨 Problemas Comuns

### 1. Container não inicia

**Sintomas:**
- `docker-compose ps` mostra status "Restarting" ou "Exit 1"
- Logs mostram erro logo após startup

**Causas Comuns:**

#### A. MASTER_KEY inválida

**Erro:**
```
ValueError: Fernet key must be 32 url-safe base64-encoded bytes
```

**Solução:**
```bash
# Gerar nova MASTER_KEY
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

# Atualizar .env
nano .env
# MASTER_KEY=<output_acima>

# Reiniciar
docker-compose down
docker-compose up -d
```

#### B. Variável de ambiente faltando

**Erro:**
```
ValidationError: field required (type=value_error.missing)
```

**Solução:**
```bash
# Verificar .env
cat .env

# Comparar com .env.example
diff .env .env.example

# Adicionar variáveis faltantes
nano .env
```

#### C. Porta 8000 já em uso

**Erro:**
```
ERROR: for api Cannot start service api: driver failed programming external connectivity
```

**Solução:**
```bash
# Ver o que está usando a porta
# Windows:
netstat -ano | findstr :8000

# Linux/Mac:
lsof -i :8000

# Matar processo ou trocar porta no docker-compose.yml
# ports:
#   - "8001:8000"  # Usar 8001 ao invés de 8000
```

---

### 2. OAuth com Conta Azul falha

#### A. "401 Unauthorized" ao trocar code por token

**Erro nos logs:**
```
ERROR: Falha ao trocar code por tokens: 401 Client Error: Unauthorized
🚨 ERRO 401 UNAUTHORIZED na troca code → tokens
```

**Causas:**
- Client ID ou Client Secret incorretos
- Authorization header mal formatado
- Credenciais de ambiente errado (sandbox vs produção)

**Solução:**
```bash
# 1. Verificar credenciais no .env
cat .env | grep CONTA_AZUL

# 2. Comparar com Portal Conta Azul
# Acessar: portal.contaazul.com → Integrações → APIs
# Copiar CLIENT_ID e CLIENT_SECRET EXATAMENTE como aparecem

# 3. Atualizar .env (sem espaços extras)
nano .env
# CONTA_AZUL_CLIENT_ID=sua_client_id_aqui
# CONTA_AZUL_CLIENT_SECRET=sua_client_secret_aqui

# 4. Reiniciar
docker-compose restart api
```

**Diagnóstico detalhado:**
```bash
# Executar script de diagnóstico
docker-compose exec api python scripts/diagnose_401.py
```

#### A1. "401 Unauthorized" ao buscar informações da conta (/v1/me)

**Erro nos logs:**
```
ERROR: Erro ao buscar informações da conta: 401
🚨 ERRO 401 UNAUTHORIZED ao buscar /v1/me
```

**Este é o erro mais comum após exchange do token!**

**Causas Comuns:**

##### 1. Token expirado ou inválido
```
Error Type: invalid_token
Description: The access token provided is expired, revoked, malformed, or invalid
```

**Solução:**
- Token pode ter expirado durante o processo
- Verificar `expires_in` no log (deve ser ~3600s)
- Refazer o fluxo OAuth completo
- Se persistir, verificar se o clock do servidor está sincronizado

##### 2. Scope insuficiente
```
Error Type: insufficient_scope
Description: The request requires higher privileges than provided by the access token
```

**Solução:**
```bash
# 1. Verificar scopes no código (services_auth.py)
cat app/services_auth.py | grep "SCOPES ="
# Deve ser: openid profile aws.cognito.signin.user.admin

# 2. No Portal Conta Azul:
#    - Integrações → APIs → Seu App
#    - Verificar PERMISSÕES DE LEITURA habilitadas
#    - Verificar SCOPES: openid, profile, aws.cognito.signin.user.admin

# 3. Revogar autorização e refazer OAuth
#    - Portal Conta Azul → Integrações → Autorizações
#    - Revogar a autorização existente
#    - Fazer novo fluxo: GET /connect
```

##### 3. App em Sandbox mas usando API de Produção
```
Error Type: invalid_token
Message: Token not valid for production API
```

**Solução:**
```bash
# Verificar ambiente do app no Portal Conta Azul
# Se app estiver em SANDBOX:
# 1. Migrar app para PRODUÇÃO, OU
# 2. Usar API de sandbox (se existir)

# URLs de Produção (padrão):
# CONTA_AZUL_AUTH_URL=https://auth.contaazul.com/login
# CONTA_AZUL_TOKEN_URL=https://auth.contaazul.com/oauth2/token
# CONTA_AZUL_API_BASE_URL=https://api.contaazul.com
```

##### 4. Audience incorreta
```
Error Type: invalid_token
Description: Token audience does not match
```

**Solução:**
```bash
# Verificar URL da API no .env
cat .env | grep API_BASE_URL
# Deve ser: https://api.contaazul.com (SEM hífen em "contaazul")

# URLs CORRETAS:
# CONTA_AZUL_API_BASE_URL=https://api.contaazul.com

# URLs INCORRETAS (não usar):
# ❌ https://api.conta-azul.com (com hífen)
# ❌ http://api.contaazul.com (sem HTTPS)
# ❌ https://api.contaazul.com.br (com .br)
```

##### 5. App sem permissões no Portal Conta Azul
```
Error Type: access_denied
Description: App does not have required permissions
```

**Solução:**
```bash
# No Portal Conta Azul (portal.contaazul.com):
# 1. Integrações → APIs → Seu App
# 2. Aba "Permissões" ou "Scopes"
# 3. Habilitar:
#    - Leitura de dados da empresa
#    - Leitura de dados financeiros
#    - Leitura de contas a receber
# 4. Salvar mudanças
# 5. Revogar autorizações antigas e refazer OAuth
```

**Verificação passo-a-passo:**
```bash
# 1. Confirmar que fluxo segue Authorization Code
cat app/services_auth.py | grep "grant_type"
# Deve ter: grant_type=authorization_code

# 2. Confirmar que usa Bearer token
cat app/services_auth.py | grep "Bearer"
# Deve ter: Authorization: Bearer {access_token}

# 3. Confirmar URLs oficiais
cat .env | grep -E "AUTH_URL|TOKEN_URL|API_BASE"
# Devem ser:
# CONTA_AZUL_AUTH_URL=https://auth.contaazul.com/login
# CONTA_AZUL_TOKEN_URL=https://auth.contaazul.com/oauth2/token
# CONTA_AZUL_API_BASE_URL=https://api.contaazul.com

# 4. Ver logs detalhados durante fluxo real
docker-compose logs -f api | grep -A 20 "Etapa 2"
# Vai mostrar diagnóstico completo do erro 401
```

**Diagnóstico automático:**
```bash
# Script de diagnóstico completo
docker-compose exec api python scripts/diagnose_401.py

# Vai verificar:
# - URLs corretas
# - Formato das credenciais
# - Base64 encoding
# - Scopes configurados
# - Testar endpoints (com tokens fake para ver erros)
```

**Log de exemplo com diagnóstico completo:**
```
🚨 ERRO 401 UNAUTHORIZED ao buscar /v1/me
================================================================================
📍 URL chamada: https://api.contaazul.com/v1/me
🔑 Token usado: eyJhbGci...xMjM=
📊 Status Code: 401

📋 Response Body:
   {'error': 'invalid_token', 'error_description': 'The access token expired'}

📋 Análise do erro:
   Error Type: invalid_token
   Description: The access token expired

💡 Possíveis causas:
   1. Token expirado (verifique expires_in do token)
   2. Token malformado ou corrompido
   3. Token de ambiente errado (sandbox vs prod)

🔧 Verificar:
   - Portal Conta Azul → Integrações → APIs
   - App em PRODUÇÃO (não sandbox)
   - Permissões de LEITURA habilitadas
   - URLs corretas no .env (auth.contaazul.com, api.contaazul.com)
================================================================================
```

**Checklist de correção:**
- [ ] Credenciais CLIENT_ID/SECRET corretas no .env
- [ ] URLs oficiais configuradas (auth.contaazul.com, api.contaazul.com)
- [ ] App em PRODUÇÃO no Portal Conta Azul
- [ ] Permissões de leitura habilitadas no app
- [ ] Scopes corretos: openid profile aws.cognito.signin.user.admin
- [ ] Token não expirado (expires_in ~3600s)
- [ ] Authorization header: `Bearer {access_token}`
- [ ] Nenhum caractere extra ou espaço nas credenciais
- [ ] REDIRECT_URI exatamente igual no Portal e .env
- [ ] Conta autorizada tem acesso aos dados

#### B. "redirect_uri_mismatch"

**Erro:**
```
The redirect URI provided is missing or does not match
```

**Causa:**
- REDIRECT_URI no `.env` ≠ Redirect URI no Portal Conta Azul

**Solução:**
```bash
# Ver REDIRECT_URI atual
cat .env | grep REDIRECT_URI

# Deve ser EXATAMENTE igual ao cadastrado no Portal
# Exemplo: https://payflow.seu-dominio.com/oauth/callback

# Se diferente, atualizar:
# 1. No Portal Conta Azul, OU
# 2. No .env

nano .env
# CONTA_AZUL_REDIRECT_URI=https://payflow.seu-dominio.com/oauth/callback

docker-compose restart api
```

#### C. Token expira rapidamente

**Sintomas:**
- Worker falha com "401 Unauthorized"
- Mensagem: "Token expired"

**Solução:**
O sistema já implementa refresh automático. Verificar logs:

```bash
docker-compose logs worker | grep -i "refresh\|expired"

# Se vir "Renovando token expirado...":
# ✅ Está funcionando corretamente

# Se vir "Falha ao renovar token":
# Verificar que refresh_token está salvo:
docker-compose exec api bash
sqlite3 data/payflow.db
sqlite> SELECT account_id, expires_at FROM oauth_tokens;
```

---

### 3. SMTP / Email falha

#### A. "535 Authentication Error" (Gmail)

**Erro:**
```
SMTPAuthenticationError: (535, '5.7.8 Username and Password not accepted')
```

**Causa:**
- Usando senha comum ao invés de App Password
- 2FA não habilitado

**Solução:**
```bash
# Gmail requer App Password, não senha comum
# 1. Habilitar 2FA: myaccount.google.com/security
# 2. Gerar App Password: myaccount.google.com/apppasswords
# 3. Copiar senha de 16 dígitos (ex: abcd efgh ijkl mnop)

# Atualizar .env (sem espaços!)
nano .env
# SMTP_PASSWORD=abcdefghijklmnop

docker-compose restart api
```

#### B. "Connection timeout"

**Erro:**
```
TimeoutError: Connection timeout
```

**Causas:**
- Firewall bloqueando porta 587
- SMTP_HOST incorreto

**Solução:**
```bash
# Testar conexão SMTP
telnet smtp.gmail.com 587

# Se falhar: firewall bloqueando
# Liberar porta 587 (SMTP STARTTLS)

# Se SMTP_HOST errado, atualizar:
nano .env
# SMTP_HOST=smtp.gmail.com  # Gmail
# SMTP_HOST=smtp.sendgrid.net  # SendGrid
# SMTP_HOST=smtp.office365.com  # Outlook

docker-compose restart api
```

#### C. "Invalid credentials" (SendGrid)

**Erro:**
```
SMTPAuthenticationError: Invalid credentials
```

**Solução:**
```bash
# SendGrid usa credenciais especiais:
nano .env
# SMTP_USER=apikey  ← LITERAL "apikey"
# SMTP_PASSWORD=SG.sua_api_key_aqui

docker-compose restart api
```

#### D. Email não chega (sem erro)

**Possíveis causas:**
- Email do destinatário incorreto
- Spam filter
- SMTP_FROM não verificado

**Solução:**
```bash
# Verificar logs
docker-compose logs api | grep -i "email\|smtp"

# Testar com email próprio
docker-compose exec api bash
python3 << 'EOF'
from app.services.mailer import MailerService
mailer = MailerService()
result = mailer.send_test_email('seu_email@gmail.com')
print(f'Resultado: {result}')
EOF

# Verificar spam folder no email de destino
# Verificar que SMTP_FROM está verificado no provedor
```

---

### 4. Worker não processa contas

**Sintomas:**
- Logs do worker mostram "Nenhuma conta ativa"
- Ou: "0 conta(s) ativa(s)"

**Causa:**
Nenhuma conta OAuth autorizada ainda

**Solução:**
```bash
# Verificar contas no banco
docker-compose exec api bash
sqlite3 data/payflow.db
sqlite> SELECT account_id, is_active FROM azul_accounts;

# Se vazio: fazer OAuth primeiro
exit  # sair do container

# Browser: https://payflow.seu-dominio.com/connect
# Autorizar aplicação

# Verificar novamente
docker-compose exec api bash
sqlite3 data/payflow.db
sqlite> SELECT account_id, is_active FROM azul_accounts;
# Agora deve aparecer 1+ linha(s)
```

---

### 5. Cloudflare Tunnel não conecta

**Sintomas:**
- `https://payflow.seu-dominio.com` retorna "502 Bad Gateway"
- Logs: "Failed to connect to tunnel"

#### A. Token inválido

**Solução:**
```bash
# Regenerar token na Cloudflare
# Dashboard → Zero Trust → Tunnels → payflow-api → Regenerate token

# Copiar novo token e atualizar .env
nano .env
# CLOUDFLARE_TUNNEL_TOKEN=<novo_token>

docker-compose down
docker-compose up -d
```

#### B. Firewall bloqueando

**Portas necessárias:**
- 80 (HTTP)
- 443 (HTTPS)
- 7844 (Cloudflare protocol)

**Solução:**
```bash
# Liberar portas (exemplo Ubuntu/Debian)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 7844/tcp
sudo ufw reload
```

#### C. DNS não propagou

**Solução:**
```bash
# Verificar DNS
nslookup payflow.seu-dominio.com

# Ou:
dig payflow.seu-dominio.com

# Esperado: CNAME apontando para *.cfargotunnel.com

# Se não aparecer: aguardar propagação DNS (até 24h)
```

---

### 6. "429 Too Many Requests" (Rate Limit)

**Sintomas:**
- Logs: "Rate limit atingido (429)"
- API Conta Azul retorna 429

**Causa:**
Muitas requisições em pouco tempo

**Solução:**
✅ O sistema já implementa **backoff exponencial** automático

Aguardar retry automático:
```bash
# Ver logs
docker-compose logs worker | grep -i "429\|retry"

# Esperado:
# WARNING: Rate limit atingido (429), aguardando...
# INFO: Tentativa 2/3...
# INFO: Sucesso após retry
```

Se persistir, aumentar intervalo de polling:
```env
# .env
POLLING_INTERVAL_SECONDS=600  # 10 minutos ao invés de 5
```

---

### 7. Banco de dados corrompido

**Sintomas:**
- `docker-compose logs api` mostra "database is locked"
- Ou: "disk I/O error"

**Solução:**
```bash
# 1. Parar serviços
docker-compose down

# 2. Verificar integridade
sqlite3 data/payflow.db "PRAGMA integrity_check;"

# Se retornar "ok": banco OK
# Se retornar erros: restaurar backup

# 3. Restaurar backup (se necessário)
cp data/payflow.db.backup.20260210_120000 data/payflow.db

# 4. Reiniciar
docker-compose up -d
```

---

### 8. Memória/CPU alta

**Sintomas:**
- Container consumindo muita memória
- CPU em 100%

**Diagnóstico:**
```bash
# Ver uso de recursos
docker stats

# Ver processos dentro do container
docker-compose exec api top
```

**Soluções:**

#### Limitar recursos:
```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          memory: 256M
```

#### Reduzir intervalo de polling:
```env
# .env
POLLING_INTERVAL_SECONDS=600  # Menos requisições
```

#### Desabilitar debug logs:
```env
# .env
LOG_LEVEL=INFO  # Ao invés de DEBUG
```

---

## 🧪 Testes de Diagnóstico

### Testar OAuth Completo

```bash
# 1. Iniciar autorização
curl http://localhost:8000/connect

# Copiar URL de redirect e abrir no browser

# 2. Autorizar na Conta Azul

# 3. Será redirecionado para /oauth/callback
# Deve aparecer mensagem de sucesso
```

### Testar SMTP

```bash
docker-compose exec api python3 << 'EOF'
from app.services.mailer import MailerService

mailer = MailerService()
result = mailer.send_test_email('seu_email@gmail.com')

if result:
    print('✅ SMTP OK')
else:
    print('❌ SMTP FALHOU')
EOF
```

### Testar Criptografia

```bash
docker-compose exec api python3 << 'EOF'
from app.crypto import get_crypto_manager

crypto = get_crypto_manager()

# Test encrypt/decrypt
plaintext = "test_token_123"
encrypted = crypto.encrypt(plaintext)
decrypted = crypto.decrypt(encrypted)

if plaintext == decrypted:
    print('✅ Criptografia OK')
else:
    print('❌ Criptografia FALHOU')
EOF
```

### Testar Banco de Dados

```bash
docker-compose exec api bash

sqlite3 data/payflow.db << 'EOF'
.tables
SELECT COUNT(*) FROM oauth_tokens;
SELECT COUNT(*) FROM azul_accounts;
.quit
EOF
```

---

## 📊 Logs Úteis

### Ver últimas requisições HTTP

```bash
docker-compose logs api | grep -E "GET|POST|PUT|DELETE"
```

### Ver erros apenas

```bash
docker-compose logs api | grep ERROR
```

### Ver processamento do worker

```bash
docker-compose logs worker | grep -E "processados|erros|Processando"
```

### Ver tokens sendo renovados

```bash
docker-compose logs worker | grep -i "refresh\|renovando"
```

---

## 🔄 Reset Completo

Se tudo falhar, reset completo:

```bash
# 1. Parar e remover containers
docker-compose down -v

# 2. Backup do banco (se necessário)
cp data/payflow.db data/payflow.db.backup.emergency

# 3. Limpar banco (CUIDADO!)
rm data/payflow.db

# 4. Rebuild imagens
docker-compose build --no-cache --pull

# 5. Reiniciar
docker-compose up -d

# 6. Verificar logs
docker-compose logs -f

# 7. Re-autorizar OAuth
# Browser: https://payflow.seu-dominio.com/connect
```

---

## 🆘 Ainda com problemas?

### Coletar informações para suporte

```bash
# Versões
docker --version
docker-compose --version
python --version

# Status
docker-compose ps

# Logs (últimas 200 linhas)
docker-compose logs --tail=200 > logs_payflow.txt

# Config (sem secrets!)
cat .env | grep -v "PASSWORD\|SECRET\|KEY\|TOKEN" > config_sanitized.txt

# Enviar logs_payflow.txt e config_sanitized.txt para suporte
```

### Contato

- GitHub Issues: (link do repositório)
- Email: suporte@seu-dominio.com
- Consultar: [README.md](README.md), [DEPLOY.md](DEPLOY.md), [SECURITY.md](SECURITY.md)

---

## 🆘 Problemas Específicos Validados

### SMTP: Erro 535 Authentication Failed

**Erro completo:**
```
SMTPAuthenticationError: (535, b'5.7.8 Error: authentication failed: (reason unavailable)')
```

**Causa:** Senha incorreta OU configuração SSL/TLS errada

**Solução por servidor:**

**skymail.net.br (porta 465):**
```env
SMTP_HOST=smtp.skymail.net.br
SMTP_PORT=465
SMTP_USE_TLS=false
SMTP_USE_SSL=true  # SSL direto
```

**Gmail (porta 587):**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
# Obrigatório: App Password (não senha comum)
# https://myaccount.google.com/apppasswords
```

**Testar:**
```bash
python scripts/test_smtp.py seu_email@gmail.com
```

---

### OAuth: "localhost não funciona para redirect_uri"

**Problema:** Conta Azul não consegue redirecionar para `http://localhost:8000/oauth/callback`

**Motivo:** OAuth externo requer URL acessível publicamente

**Soluções validadas:**

**1. Cloudflare Tunnel (Produção - Recomendado):**
```bash
# .env
CONTA_AZUL_REDIRECT_URI=https://payflow.ctrls.dev.br/oauth/callback

# Subir Docker
docker-compose up -d

# OAuth via browser
https://payflow.ctrls.dev.br/connect
```

**2. ngrok (Desenvolvimento):**
```bash
# Terminal 1
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2
ngrok http 8000
# Output: https://abc-123.ngrok.io

# Usar no .env E no painel Conta Azul:
CONTA_AZUL_REDIRECT_URI=https://abc-123.ngrok.io/oauth/callback
```

---

### OAuth: URLs Corretas (Validadas com Painel Real)

**URLs que funcionam:**
```
Authorize: https://auth.contaazul.com/login
Token: https://auth.contaazul.com/oauth2/token
Scope: openid profile aws.cognito.signin.user.admin
```

**URLs antigas (NÃO usar):**
```
❌ https://api.contaazul.com/auth/authorize
❌ https://accounts.contaazul.com/oauth/authorize
❌ Scope: sale (documentação antiga)
```

---

**Última atualização:** 2026-02-11

