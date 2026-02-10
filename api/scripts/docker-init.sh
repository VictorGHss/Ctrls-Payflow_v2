#!/bin/bash
# Script para inicializar deploy do PayFlow

set -e

echo "=========================================="
echo "   PayFlow Initialization Script"
echo "=========================================="
echo ""

# Verificar pré-requisitos
echo "[1/5] Verificando pré-requisitos..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker não encontrado. Instale em https://docs.docker.com/install/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose não encontrado. Instale em https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker e Docker Compose encontrados"
echo ""

# Verificar .env
echo "[2/5] Verificando .env..."

if [ ! -f .env ]; then
    echo "❌ Arquivo .env não encontrado"
    echo "   Executar: cp .env.example .env"
    exit 1
fi

# Verificar parâmetros essenciais
if ! grep -q "CONTA_AZUL_CLIENT_ID" .env; then
    echo "❌ .env incompleto: CONTA_AZUL_CLIENT_ID ausente"
    exit 1
fi

if ! grep -q "CLOUDFLARE_TUNNEL_TOKEN" .env; then
    echo "⚠️  CLOUDFLARE_TUNNEL_TOKEN não configurado (será necessário mais tarde)"
fi

echo "✅ .env encontrado e válido"
echo ""

# Criar diretório de dados
echo "[3/5] Preparando volumes..."

mkdir -p data
chmod 755 data

echo "✅ Diretório data criado"
echo ""

# Build das imagens
echo "[4/5] Building Docker images..."

docker-compose build

echo "✅ Docker images built"
echo ""

# Rodar containers
echo "[5/5] Iniciando containers..."

docker-compose up -d

echo "✅ Containers iniciados"
echo ""

# Verificar status
echo "=========================================="
echo "   Status dos Containers"
echo "=========================================="

docker-compose ps

echo ""
echo "=========================================="
echo "   Próximos Passos"
echo "=========================================="
echo ""
echo "1. Verificar logs da API:"
echo "   docker-compose logs -f api"
echo ""
echo "2. Testar healthcheck:"
echo "   curl http://localhost:8000/healthz"
echo ""
echo "3. Acessar Swagger UI:"
echo "   http://localhost:8000/docs"
echo ""
echo "4. Para configurar Cloudflare Tunnel:"
echo "   - Acessar https://dash.cloudflare.com"
echo "   - Ir em Zero Trust → Tunnels"
echo "   - Criar um novo tunnel e copiar o token"
echo "   - Adicionar ao .env: CLOUDFLARE_TUNNEL_TOKEN=..."
echo "   - Rodar: docker-compose up -d"
echo ""
echo "5. Para ver logs em tempo real:"
echo "   docker-compose logs -f"
echo ""
echo "6. Para parar containers:"
echo "   docker-compose down"
echo ""

echo "✅ PayFlow inicializado com sucesso!"

