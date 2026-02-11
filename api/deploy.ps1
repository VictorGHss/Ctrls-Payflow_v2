#!/usr/bin/env pwsh
# Script de deployment para aplicar as correções da API v2

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "🚀 DEPLOYMENT - Correção API v2 da Conta Azul" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Verificar se estamos no diretório correto
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "❌ Erro: docker-compose.yml não encontrado!" -ForegroundColor Red
    Write-Host "Execute este script no diretório /api" -ForegroundColor Red
    exit 1
}

Write-Host "📋 Verificando arquivos modificados..." -ForegroundColor Yellow
$files_modified = @(
    "app/config.py",
    "app/services_auth.py",
    "app/routes_oauth.py",
    "app/worker/conta_azul_financial_client.py",
    ".env",
    ".env.example"
)

foreach ($file in $files_modified) {
    if (Test-Path $file) {
        Write-Host "  ✅ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file não encontrado" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "🧪 Executando testes de validação..." -ForegroundColor Yellow
python scripts/test_api_v2.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Testes falharam! Revise as alterações antes de continuar." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🐳 Parando containers..." -ForegroundColor Yellow
docker-compose down

Write-Host ""
Write-Host "🔨 Rebuilding containers..." -ForegroundColor Yellow
docker-compose up -d --build

Write-Host ""
Write-Host "⏳ Aguardando containers iniciarem..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "📊 Status dos containers:" -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "📝 Logs recentes:" -ForegroundColor Yellow
docker-compose logs --tail=50 api

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "✅ DEPLOYMENT CONCLUÍDO!" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "Próximos passos:" -ForegroundColor Yellow
Write-Host "  1. Testar o fluxo OAuth: https://payflow.ctrls.dev.br/oauth/authorize" -ForegroundColor White
Write-Host "  2. Verificar logs: docker-compose logs -f api" -ForegroundColor White
Write-Host "  3. Monitorar chamadas à API v2 nos logs" -ForegroundColor White
Write-Host ""
Write-Host "Endpoints agora usam:" -ForegroundColor Yellow
Write-Host "  - Auth: https://auth.contaazul.com" -ForegroundColor White
Write-Host "  - API:  https://api-v2.contaazul.com" -ForegroundColor White
Write-Host ""

