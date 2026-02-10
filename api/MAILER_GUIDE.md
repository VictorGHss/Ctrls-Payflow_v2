# 📧 Serviço de Email - SMTP com TLS

Serviço robusto de envio de email via SMTP com TLS obrigatório.

## 📋 Características

✅ **SMTP com TLS**
- STARTTLS obrigatório
- Timeout configurável
- Autenticação segura

✅ **Validação Robusta**
- Validação de email (From, To, Reply-To)
- Validação de PDF (magic bytes, tamanho)
- Sanitização de subject (prevenção de injection)

✅ **Segurança**
- Senha SMTP nunca é loggada
- Sem logging de conteúdo de email
- Sem logging de PDFs

✅ **Tratamento de Erros**
- Timeouts controlados
- Retry logic (em camada superior)
- Mensagens de erro limpas

✅ **Testes Completos**
- 30+ testes automatizados
- Mock de SMTP (sem enviar de verdade)
- Cobertura de casos de erro

## 🔧 Configuração

### .env

```env
SMTP_HOST=smtp.seuhost.com
SMTP_PORT=587
SMTP_USER=seu_email@dominio.com
SMTP_PASSWORD=sua_senha_smtp
SMTP_FROM=seu_email@dominio.com
SMTP_REPLY_TO=seu_email@dominio.com
SMTP_USE_TLS=true
SMTP_TIMEOUT=10
```

### app/config.py

```python
SMTP_HOST: str
SMTP_PORT: int = 587
SMTP_USER: str
SMTP_PASSWORD: str
SMTP_FROM: str
SMTP_REPLY_TO: str = ""
SMTP_USE_TLS: bool = True
SMTP_TIMEOUT: int = 10  # segundos
```

## 📚 API

### MailerService

```python
from app.services.mailer import MailerService

mailer = MailerService()

# Enviar email com recibo
success = mailer.send_receipt_email(
    doctor_email="doctor@example.com",
    customer_name="João Silva",
    amount=1000.50,
    receipt_date="2026-02-10",
    pdf_content=pdf_bytes,
    pdf_filename="recibo.pdf",
    reply_to="reply@example.com"  # opcional
)

# Enviar email de teste
success = mailer.send_test_email("test@example.com")
```

### Parâmetros

```python
def send_receipt_email(
    doctor_email: str,          # Email do destinatário
    customer_name: str,         # Nome do cliente/paciente
    amount: float,              # Valor da transação
    receipt_date: Optional[str],# Data ISO ou similar
    pdf_content: bytes,         # Conteúdo do PDF
    pdf_filename: str,          # Nome do arquivo (*.pdf)
    reply_to: Optional[str] = None,  # Email de reply (opcional)
) -> bool:                      # True se sucesso
```

## 🔐 Segurança

### TLS Obrigatório
- Usa STARTTLS na porta 587
- Não permite envio sem TLS

### Validação de Email
```python
# Valida format de email
- user@domain.com ✓
- invalid ✗
- @example.com ✗
- user@ ✗
```

### Validação de PDF
```python
# Valida:
- Magic bytes (%PDF)
- Tamanho (1KB - 25MB)
- Extensão (.pdf)
```

### Sanitização de Subject
```python
# Previne injection SMTP:
- Remove newlines (\n, \r)
- Limita tamanho (100 chars)
- Escapa caracteres especiais
```

### Sem Logging Sensível
- Senha SMTP: nunca é loggada
- Conteúdo email: não loggado
- PDFs: não loggados
- Apenas eventos estruturados

## 🧪 Testes

30+ testes automatizados com mock de SMTP.

### Rodar Testes

```bash
pytest tests/test_mailer.py -v
```

### Cobertura

**Validação de Config (2)**
- Config válida
- Config inválida

**Validação de Email (2)**
- Email válido
- Email inválido

**Sanitização de Subject (3)**
- Newline injection
- Comprimento
- Subject normal

**Validação de PDF (5)**
- PDF válido
- Conteúdo vazio
- Arquivo muito grande
- Extensão inválida
- Magic bytes inválidos

**Construção de Mensagem (4)**
- Subject
- Body
- Body minimal
- Mensagem completa

**Envio SMTP (3)**
- Sucesso
- Erro de auth
- Timeout

**Envio Completo (4)**
- Sucesso
- Email inválido
- Anexo inválido
- Erro SMTP

**Email de Teste (2)**
- Sucesso
- Endereço inválido

## 📧 Exemplo de Corpo de Email

```
Prezado(a),

Segue em anexo o recibo referente ao pagamento realizado.

Cliente: João Silva
Valor: R$ 1000.50
Data: 2026-02-10

Atenciosamente,
Sistema de Gestão Financeira
```

## ⚙️ Detalhes de Implementação

### Fluxo de Envio

1. **Validação de Config**
   - Verifica SMTP_HOST, PORT, USER, PASSWORD, FROM
   - Valida SMTP_FROM é email válido

2. **Validação de Parâmetros**
   - Email do destinatário é válido
   - Email de reply-to (se fornecido) é válido
   - PDF tem magic bytes %PDF
   - PDF tamanho entre 1KB e 25MB
   - Extensão é .pdf

3. **Construção da Mensagem**
   - Subject: "Recibo de pagamento - {customer_name}"
   - Body: Informações mínimas (sem vazar dados)
   - Attachments: PDF anexado
   - Headers: From, To, Reply-To (se fornecido)

4. **Envio via SMTP**
   - Conexão com timeout
   - STARTTLS ativo
   - Autenticação
   - Envio da mensagem
   - Conexão fechada

### Tratamento de Erros

```python
# Erros esperados:
- SMTPConfigError      → Config inválida
- EmailValidationError → Email/PDF inválido
- SMTPAuthenticationError → Credenciais inválido
- TimeoutError        → Timeout na conexão
```

## 📊 Exemplo de Uso Completo

```python
from app.services.mailer import MailerService

try:
    mailer = MailerService()
    
    success = mailer.send_receipt_email(
        doctor_email="dr.silva@hospital.com",
        customer_name="Maria Santos",
        amount=1500.00,
        receipt_date="2026-02-10T15:30:00Z",
        pdf_content=pdf_bytes,
        pdf_filename="recibo_2026-02-10.pdf",
        reply_to="financeiro@empresa.com"
    )
    
    if success:
        print("Email enviado com sucesso!")
    else:
        print("Falha ao enviar email")
        
except Exception as e:
    print(f"Erro: {e}")
```

## 🔗 Integração com Worker

O MailerService é usado pelo FinancialProcessor:

```python
from app.services.mailer import MailerService

class FinancialProcessor:
    def __init__(self, db):
        self.mailer = MailerService()
    
    async def _process_attachment(self, ...):
        success = self.mailer.send_receipt_email(
            doctor_email=doctor_email,
            customer_name=customer_name,
            amount=amount,
            receipt_date=payment_date,
            pdf_content=pdf_bytes,
            pdf_filename=filename,
            reply_to=self.settings.SMTP_REPLY_TO or None,
        )
```

## 🚀 Próximos Passos

- [ ] Suporte a attachment múltiplos
- [ ] Template de email customizável
- [ ] Queue de emails (async job queue)
- [ ] Retry automático de falhas
- [ ] Webhook de status de entrega
- [ ] Rate limiting de envio
- [ ] Logging estruturado para auditoria

---

**Status**: ✅ Production Ready

Desenvolvido com segurança, validação robusta e testes completos.

