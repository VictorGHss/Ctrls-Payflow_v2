# 🚀 DEPLOY - Guia Completo

Guia passo-a-passo para fazer deploy do PayFlow com Docker e Cloudflare Tunnel + Access.

## 📋 Pré-requisitos

### No seu Servidor Local (Home Server/VPS)
- Docker instalado (`docker --version`)
- Docker Compose instalado (`docker-compose --version`)
- Git (para clonar o repositório)
- Acesso sudo/root

### Na Cloudflare
- Conta Cloudflare ativa
- Domínio registrado e apontando para Cloudflare
- (Opcional) Google OAuth configurado

## 🔧 Passo 1: Clonar Repositório

```bash
# No seu servidor
git clone https://github.com/seu-usuario/payflow.git
cd payflow/api
```

## 📝 Passo 2: Configurar .env

```bash
cp .env.example .env
nano .env  # ou editor de sua preferência
```

Preencher:
```env
# Conta Azul
CONTA_AZUL_CLIENT_ID=seu_client_id
CONTA_AZUL_CLIENT_SECRET=seu_client_secret
CONTA_AZUL_REDIRECT_URI=https://seu-dominio.com/oauth/callback

# Segurança
MASTER_KEY=base64_encoded_32_bytes
JWT_SECRET=seu_jwt_secret

# SMTP
SMTP_HOST=smtp.seuhost.com
SMTP_PORT=587
SMTP_USER=seu_email@dominio.com
SMTP_PASSWORD=sua_senha_smtp
SMTP_FROM=seu_email@dominio.com
SMTP_REPLY_TO=seu_email@dominio.com
SMTP_USE_TLS=true
SMTP_TIMEOUT=10

# Polling
POLLING_INTERVAL_SECONDS=300
POLLING_SAFETY_WINDOW_MINUTES=10

# Database
DATABASE_URL=sqlite:///./data/payflow.db

# Será configurado depois
CLOUDFLARE_TUNNEL_TOKEN=<será gerado na Cloudflare>
```

## ☁️ Passo 3: Criar Tunnel na Cloudflare

### 3.1 Acessar Cloudflare Dashboard

1. Acessar https://dash.cloudflare.com
2. Selecionar seu domínio
3. Clicar em **Zero Trust** no menu lateral esquerdo
4. Clicar em **Tunnels** (ou **Tunnels & Connectors** → **Tunnels**)

### 3.2 Criar Novo Tunnel

```
Tunnels → Create a tunnel
├─ Tunnel name: payflow (ou seu nome)
├─ Connector: Docker (você vai usar Docker)
└─ Next
```

### 3.3 Copiar Token

Na próxima tela, você verá um comando como:

```bash
cloudflared tunnel run --token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Copie apenas a parte do token** (string longa após `--token`):

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 3.4 Salvar Token no .env

```bash
# No seu servidor, editar .env
nano .env
```

Colar:
```env
CLOUDFLARE_TUNNEL_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Salvar e fechar.

### 3.5 Configurar Public Hostnames

Voltar ao Cloudflare, na aba **Public Hostnames**:

```
Public Hostnames → Create hostname
├─ Subdomain: payflow (ou api)
├─ Domain: seu-dominio.com
├─ Type: HTTPS
├─ URL: http://api:8000  (nome do container Docker + porta interna)
└─ Save
```

**Importante**: URL é `http://api:8000` (não localhost), porque dentro do Docker o serviço se chama "api".

Agora seu app estará disponível em: `https://payflow.seu-dominio.com`

## 🔐 Passo 4: Proteger com Cloudflare Access (Google SSO)

### 4.1 Acessar Cloudflare Access

```
Zero Trust → Access → Applications
├─ Create Application
└─ Self-hosted
```

### 4.2 Configurar Aplicação

```
Application name: PayFlow API
Subdomain: payflow
Domain: seu-dominio.com
Application type: Self-hosted
```

### 4.3 Configurar Autenticação (Google SSO)

Nas páginas seguintes:

```
Policies → Add a policy
├─ Policy name: "Require Google Account"
├─ Action: Allow
├─ Rule:
│  ├─ Include:
│  │  └─ Selector: Emails
│  │     Valor: seu_email@gmail.com  (suas contas autorizadas)
│  └─ Exclude: (deixar vazio)
└─ Save
```

### 4.4 Adicionar Mais Usuários (Opcional)

```
Policies → Edit policy
├─ Include:
│  └─ Selector: Emails
│     Valor: email1@gmail.com, email2@gmail.com, ...
└─ Save
```

## 🐳 Passo 5: Rodar Docker Compose

```bash
# No diretório da API
cd ~/payflow/api

# Verificar que .env está pronto
cat .env  # confirmar que CLOUDFLARE_TUNNEL_TOKEN está preenchido

# Build da imagem (primeira vez)
docker-compose build

# Rodar os serviços
docker-compose up -d

# Verificar status
docker-compose ps
```

Esperado:
```
NAME                    STATUS
payflow-api             Up (healthy)
payflow-worker          Up
payflow-cloudflared     Up
```

## ✅ Passo 6: Verificar Deployments

### 6.1 Verificar Logs

```bash
# Logs da API
docker-compose logs -f api

# Logs do Worker
docker-compose logs -f worker

# Logs do Cloudflared
docker-compose logs -f cloudflared
```

Esperado na API:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     PayFlow API iniciada - 1.0.0
```

Esperado no Worker:
```
Worker iniciado
Intervalo de polling: 300s
```

### 6.2 Testar Endpoint

```bash
# Localmente no servidor
curl http://localhost:8000/healthz

# Esperado
{"status":"ok"}
```

### 6.3 Testar via Cloudflare Tunnel

```bash
# Acessar no browser
https://payflow.seu-dominio.com/docs

# Você será redirecionado para Google login
# Após autenticar, verá Swagger UI
```

## 🔄 Passo 7: Acessar Aplicação

### Login via Google SSO

1. Abrir `https://payflow.seu-dominio.com`
2. Será redirecionado para login do Google
3. Autenticar com conta configurada no Cloudflare Access
4. Será redirecionado para Dashboard do PayFlow

### Endpoints Disponíveis

```
GET  /healthz               Health check
GET  /ready                 Readiness check
GET  /docs                  Swagger UI
GET  /connect               Iniciar OAuth Conta Azul
GET  /oauth/callback        Callback OAuth
```

## 🛠️ Manutenção

### Ver Status

```bash
docker-compose ps
docker-compose logs -f api
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

### Atualizar Aplicação

```bash
# Parar
docker-compose down

# Puxar novo código
git pull

# Rebuild e rodar
docker-compose up -d --build
```

### Verificar Banco de Dados

```bash
# Entrar no container da API
docker-compose exec api bash

# Dentro do container
sqlite3 data/payflow.db
sqlite> SELECT COUNT(*) FROM azul_accounts;
sqlite> .exit
```

## 📊 Monitoramento

### Ver Uso de Recursos

```bash
docker stats payflow-api payflow-worker payflow-cloudflared
```

### Ver Tamanho do Banco

```bash
du -h ./data/payflow.db
```

### Backup do Banco

```bash
# Criar backup
cp ./data/payflow.db ./data/payflow.db.backup.$(date +%Y%m%d_%H%M%S)

# Listar backups
ls -lh ./data/payflow.db*
```

## 🐛 Troubleshooting

### API não inicia

```bash
# Ver logs
docker-compose logs api

# Verificar .env
cat .env | grep -v PASSWORD

# Verificar permissões
ls -la ./data/
```

### Worker não conecta

```bash
# Ver logs
docker-compose logs worker

# Verificar token OAuth
cat .env | grep CONTA_AZUL

# Verificar checkpoint
docker-compose exec api sqlite3 data/payflow.db \
  "SELECT * FROM financial_checkpoints;"
```

### Cloudflare não funciona

```bash
# Ver logs
docker-compose logs cloudflared

# Verificar token
cat .env | grep CLOUDFLARE_TUNNEL_TOKEN

# Testar localmente
curl http://localhost:8000/healthz
```

### Banco de dados corrompido

```bash
# Backup
cp ./data/payflow.db ./data/payflow.db.broken

# Recrear banco (vai perder dados)
rm ./data/payflow.db

# Reiniciar (criará novo banco)
docker-compose restart api
```

## 🔐 Segurança

### Proteger Secretos

```bash
# Nunca fazer commit de .env
echo ".env" >> .gitignore

# Permissões
chmod 600 .env

# Verificar que não há secrets no código
grep -r "MASTER_KEY\|JWT_SECRET" app/
# Não deve retornar nada (exceto variáveis de config)
```

### HTTPS Obrigatório

- Cloudflare Tunnel força HTTPS automaticamente
- Certificado é gerenciado pela Cloudflare
- Renovação automática

### Backup de Banco

```bash
# Cron job para backup diário (no servidor)
0 2 * * * cd ~/payflow/api && cp data/payflow.db data/backups/payflow.db.$(date +\%Y\%m\%d)
```

## 📞 Suporte

### Logs Importantes

```bash
# Exportar todos os logs
docker-compose logs > logs.txt

# Ver apenas erros
docker-compose logs | grep -i error
```

### Dados Úteis para Suporte

```bash
# Versões
docker --version
docker-compose --version

# Configuração (sem secrets)
cat .env | grep -v PASSWORD | grep -v SECRET | grep -v KEY | grep -v TOKEN

# Status dos containers
docker-compose ps

# Uso de recursos
docker stats

# Espaço em disco
df -h
```

## 📝 Checklist de Deploy

- [ ] Git repository clonado
- [ ] .env configurado com todas as variáveis
- [ ] Tunnel criado na Cloudflare
- [ ] CLOUDFLARE_TUNNEL_TOKEN adicionado ao .env
- [ ] Public Hostname configurado (payflow.seu-dominio.com → http://api:8000)
- [ ] Cloudflare Access configurado com Google SSO
- [ ] docker-compose build executado
- [ ] docker-compose up -d funcionando
- [ ] docker-compose ps mostra 3 containers healthy
- [ ] curl localhost:8000/healthz retorna {"status":"ok"}
- [ ] https://payflow.seu-dominio.com funciona
- [ ] Google login funciona
- [ ] Swagger UI acessível (/docs)
- [ ] Worker está processando (verificar logs)
- [ ] Banco de dados existe (data/payflow.db)

## 🎉 Deploy Concluído!

Seu PayFlow está rodando:
- ✅ API em `https://payflow.seu-dominio.com`
- ✅ Protegido com Google SSO via Cloudflare Access
- ✅ Worker processando contas a receber
- ✅ HTTPS obrigatório e certificado auto-renovado
- ✅ Banco SQLite persistente em ./data
- ✅ Usuário não-root no Docker

---

**Versão**: 1.0.0  
**Data**: 2026-02-10  
**Última atualização**: 2026-02-10

