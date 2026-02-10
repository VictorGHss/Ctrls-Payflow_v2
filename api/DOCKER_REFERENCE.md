# 🚀 Docker & Deploy - Referência Rápida

## ⚡ Comandos Essenciais

### Build e Run

```bash
# Build das imagens
docker-compose build

# Rodar tudo
docker-compose up -d

# Rodar com logs visíveis
docker-compose up

# Parar tudo
docker-compose down

# Parar e remover volumes (cuidado!)
docker-compose down -v
```

### Logs

```bash
# Todos os logs
docker-compose logs

# Logs em tempo real
docker-compose logs -f

# Apenas API
docker-compose logs -f api

# Apenas Worker
docker-compose logs -f worker

# Apenas últimas 100 linhas
docker-compose logs --tail=100
```

### Status

```bash
# Ver containers
docker-compose ps

# Ver recursos
docker stats

# Ver imagens
docker images | grep payflow

# Ver volumes
docker volume ls
```

### Executar Comandos

```bash
# Entrar no container da API
docker-compose exec api bash

# Executar comando único
docker-compose exec api curl http://localhost:8000/healthz

# Verificar banco de dados
docker-compose exec api sqlite3 data/payflow.db ".tables"
```

## 📋 Estrutura

```
Dockerfile
  ├─ Stage 1: Builder (compilar deps)
  ├─ Stage 2: Runtime (imagem final)
  └─ User: appuser (não-root)

docker-compose.yml
  ├─ api (FastAPI + Uvicorn)
  │  └─ Porta 8000, healthcheck
  ├─ worker (Python async loop)
  │  └─ Polling de contas a receber
  └─ cloudflared (Tunnel remoto)
     └─ Acesso remoto via Cloudflare

.dockerignore
  └─ Otimização de build
```

## 🔧 Volumes

```bash
# ./data → /app/data (SQLite database)
# Persistente entre restarts
# Propriedade: appuser (uid 1000)
```

## ✅ Healthcheck

```bash
# API
curl http://localhost:8000/healthz
# {"status":"ok"}

# Status no docker-compose
docker-compose ps
# payflow-api    Up (healthy)
```

## 🌐 Cloudflare Tunnel

```bash
# Token via environment
CLOUDFLARE_TUNNEL_TOKEN=eyJhbGciOi...

# Comando
cloudflared tunnel --no-autoupdate run

# URL pública
https://payflow.seu-dominio.com
```

## 🔐 Segurança

✅ Usuário não-root (appuser)
✅ Multi-stage build
✅ Minimal image size
✅ .dockerignore otimizado
✅ .env não versionado
✅ Secrets via environment

## 📊 Exemplo: Scale

```bash
# Não é recomendado escalar worker (único por conta)
# Mas pode escalar API se necessário:

docker-compose up -d --scale api=2  # 2 instâncias da API
```

## 🐛 Debug

```bash
# Build com output
docker-compose build --no-cache

# Run com verbose
docker-compose -f docker-compose.yml config

# Ver variáveis de environment
docker-compose exec api env | grep -i payflow

# Verificar conectividade entre containers
docker-compose exec api ping worker
docker-compose exec worker ping api
```

## 📦 Produção

```bash
# 1. Usar image registry (Docker Hub, ECR, etc)
# 2. Separar .env em secrets (Kubernetes, Docker Swarm)
# 3. Adicionar reverse proxy (Nginx, Traefik)
# 4. Usar managed database (PostgreSQL em vez de SQLite)
# 5. CI/CD pipeline (GitHub Actions, GitLab CI)
# 6. Monitoring (Prometheus, Grafana)
# 7. Logging centralizado (ELK, Splunk)
```

## 🔄 Workflow Típico

```bash
# 1. Fazer código
git add .
git commit -m "novo feature"

# 2. Update imagem
docker-compose build

# 3. Deploy
docker-compose up -d

# 4. Verificar
docker-compose ps
docker-compose logs -f

# 5. Rollback (se necessário)
git revert HEAD
docker-compose build
docker-compose up -d
```

## 📈 Performance

```bash
# Otimizações aplicadas:
- Multi-stage build (reduz tamanho final)
- Alpine base (python:3.10-slim)
- .dockerignore otimizado
- Layer caching
- Health checks rápidos (curl)

# Tamanho esperado:
- Final image: ~250-300MB
- Buildkit cache: ~500MB
```

## 🆘 Problemas Comuns

### Container não inicia
```bash
docker-compose logs api
# Verificar .env
# Verificar permissões em ./data
```

### Conexão recusada
```bash
# Verificar portas
netstat -tlnp | grep 8000
# Verificar firewall
sudo ufw allow 8000/tcp
```

### Banco corrompido
```bash
# Backup
cp data/payflow.db data/payflow.db.broken

# Recrear
rm data/payflow.db
docker-compose restart api
# Criará novo banco automaticamente
```

### Cloudflare não funciona
```bash
# Verificar token
echo $CLOUDFLARE_TUNNEL_TOKEN

# Verificar logs
docker-compose logs cloudflared

# Testar localmente
curl -v http://localhost:8000/healthz
```

---

Para guia completo: veja DEPLOY.md

