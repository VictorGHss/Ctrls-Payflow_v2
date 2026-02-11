# Scripts Utilitários

Scripts auxiliares para desenvolvimento e manutenção do PayFlow.

## 📁 Conteúdo

### Setup e Instalação

**`install_deps.ps1`** (Windows PowerShell)
```powershell
.\scripts\install_deps.ps1
```
Instala dependências Python no Windows.

**`install_deps.sh`** (Linux/Mac)
```bash
bash scripts/install_deps.sh
```
Instala dependências Python no Linux/Mac.

**`init_local.py`**
```bash
python scripts/init_local.py
```
Inicializa banco de dados local e cria estrutura inicial.

---

### Segurança

**`generate_key.py`**
```bash
python scripts/generate_key.py
```
Gera MASTER_KEY segura (32 bytes base64-encoded) para criptografia.

**Output:**
```
MASTER_KEY=AbCdEfGhIjKlMnOpQrStUvWxYz0123456789+/==
```

---

### Testes

**`test_oauth_flow.py`** ⭐ NOVO
```bash
python scripts/test_oauth_flow.py
```
Teste interativo completo do fluxo OAuth2:
- Gera URL de autorização
- Troca code por tokens
- Salva tokens criptografados
- Valida refresh token

**Uso:**
1. Rodar script
2. Copiar URL e abrir no navegador
3. Autorizar na Conta Azul
4. Colar code no script
5. Verificar tokens no banco

**`test_smtp.py`** ⭐ NOVO
```bash
python scripts/test_smtp.py seu_email@gmail.com
```
Teste isolado de SMTP:
- Valida configuração SMTP
- Cria PDF de teste
- Envia email real
- Verifica se chegou

**`test_oauth.py`**
```bash
python scripts/test_oauth.py
```
Teste interativo do fluxo OAuth2 com Conta Azul.

**`test_oauth_runner.py`**
```bash
python scripts/test_oauth_runner.py
```
Runner automatizado de testes OAuth2.

**`test_api.py`**
```bash
python scripts/test_api.py
```
Testa endpoints da API (health checks, OAuth, etc).

---

### Manutenção

**`manage.py`**
```bash
python scripts/manage.py <comando>
```
Gerenciamento do sistema (migrations, backup, etc).

Comandos disponíveis:
- `migrate` - Rodar migrations Alembic
- `backup` - Fazer backup do banco
- `restore <backup_file>` - Restaurar backup

**`docker-init.sh`**
```bash
bash scripts/docker-init.sh
```
Script de inicialização executado no container Docker (usado pelo Dockerfile).

---

## 🚀 Uso Rápido

### Primeira vez (Setup)

```bash
# 1. Instalar dependências
# Windows:
.\scripts\install_deps.ps1

# Linux/Mac:
bash scripts/install_deps.sh

# 2. Gerar MASTER_KEY
python scripts/generate_key.py
# Copiar output para .env

# 3. Inicializar banco
python scripts/init_local.py

# 4. Testar API
python scripts/test_api.py
```

### Testar OAuth

```bash
# Teste interativo
python scripts/test_oauth.py

# Seguir instruções na tela
```

### Backup do Banco

```bash
# Fazer backup
python scripts/manage.py backup

# Restaurar backup
python scripts/manage.py restore data/payflow.db.backup.20260210_120000
```

---

## 📝 Notas

- Scripts de setup (`install_deps.*`) são opcionais se usar Docker
- `docker-init.sh` é apenas para uso interno do container
- Scripts de teste (`test_*.py`) requerem API rodando
- `manage.py` requer banco de dados inicializado

---

**Veja também:**
- [README.md](../README.md) - Documentação principal
- [DEPLOY.md](../DEPLOY.md) - Guia de deploy
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - Solução de problemas

