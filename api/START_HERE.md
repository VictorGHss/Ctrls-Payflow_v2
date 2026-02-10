# 🚀 COMECE AQUI - PayFlow API

## ⚡ 5 Minutos para Rodar

### Passo 1: Gerar MASTER_KEY (1 min)

```bash
python scripts/generate_key.py
```

**Copie o output em local seguro!**

### Passo 2: Criar .env (2 min)

```bash
cp .env.example .env
```

Editar o arquivo com seus dados:
```env
CONTA_AZUL_CLIENT_ID=seu_client_id
CONTA_AZUL_CLIENT_SECRET=seu_client_secret
CONTA_AZUL_REDIRECT_URI=http://localhost:8000/oauth/callback

MASTER_KEY=<copiar_do_passo_1>
JWT_SECRET=seu_jwt_secret

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_app_password
SMTP_FROM=seu_email@gmail.com
SMTP_REPLY_TO=seu_email@gmail.com

DATABASE_URL=sqlite:///./data/payflow.db
```

### Passo 3: Instalar Dependências (1 min)

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Passo 4: Rodar API (1 min)

```bash
uvicorn app.main:app --reload --port 8000
```

Acesse: **http://localhost:8000/docs** ✅

### Passo 5: Rodar Worker (em outro terminal)

```bash
.\.venv\Scripts\Activate.ps1
python -m app.worker
```

## ✅ Pronto!

Sua API está rodando em `http://localhost:8000` 🎉

---

## 📚 Próximas Leituras

Após 5 minutos rodando:

1. **README.md** (30 min) - Guia completo
2. **ARCHITECTURE.md** (30 min) - Como funciona
3. **PRODUCTION.md** (1h) - Se for para produção

---

## 🧪 Rodar Testes

```bash
pytest tests/ -v
```

Esperado: todos passando ✅

---

## 🐳 Rodar com Docker

```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
```

---

## 💡 Dicas

- **Documentação completa**: README.md
- **Exemplos JSON**: PAYLOADS.md
- **Troubleshooting**: README.md → Troubleshooting
- **Produção**: PRODUCTION.md
- **Índice de tudo**: INDEX.md

---

## 🆘 Problemas Comuns

### "MASTER_KEY deve ser 32 bytes"
```bash
python scripts/generate_key.py
# Copie para .env
```

### "ModuleNotFoundError"
```bash
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### "Connection refused" (banco)
```bash
mkdir data
# Banco criado automaticamente
```

---

**Status**: ✅ Ready to use!  
**Tempo**: 5 minutos até rodar  
**Documentação**: 230KB+ incluída

**Comece agora! 🚀**

