# Payloads de Exemplo

## 1. OAuth Token Response

Quando o usuário autoriza no portal Conta Azul:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "scope": "accounts.read installments.read receipts.read"
}
```

## 2. Account Info Response

```json
{
  "id": "account_123abc",
  "email": "owner@company.com",
  "name": "João Silva",
  "companyName": "Med Clinic XYZ",
  "phone": "(11) 3000-0000",
  "document": "12.345.678/0001-90"
}
```

## 3. Installments List Response

```json
{
  "data": [
    {
      "id": "inst_001",
      "status": "received",
      "customerName": "Paciente João",
      "customerEmail": "joao@patient.com",
      "amount": 500.00,
      "receivedDate": "2025-02-10T10:30:00Z",
      "modifiedDate": "2025-02-10T10:30:00Z",
      "description": "Consulta - Fevereiro",
      "receiptUrl": "https://api.contaazul.com/v1/receipts/rec_001/download",
      "doctorEmail": "medico@clinic.com",
      "documentNumber": "12345"
    },
    {
      "id": "inst_002",
      "status": "pending",
      "customerName": "Paciente Maria",
      "amount": 300.00,
      "receivedDate": null,
      "modifiedDate": "2025-02-09T15:00:00Z",
      "receiptUrl": null,
      "doctorEmail": null
    }
  ],
  "pagination": {
    "page": 1,
    "totalPages": 1,
    "pageSize": 20,
    "totalCount": 2
  }
}
```

## 4. Database: oauth_tokens (criptografado)

```json
{
  "id": 1,
  "account_id": "account_123abc",
  "access_token": "gAAAAABlvZ0UH9k-K_zR3dM0X5j8L9mNoPqRsTu...",
  "refresh_token": "gAAAAABlvZ0UH9k-K_zR3dM0X5j8L9mNoPqRsTu...",
  "expires_at": "2025-02-10T11:30:00Z",
  "created_at": "2025-02-10T10:30:00Z",
  "updated_at": "2025-02-10T10:30:00Z"
}
```

(Tokens são criptografados via Fernet - MASTER_KEY)

## 5. Database: sent_receipts (registro de envios)

```json
{
  "id": 1,
  "account_id": "account_123abc",
  "installment_id": "inst_001",
  "receipt_id": "rec_001",
  "receipt_url": "https://api.contaazul.com/v1/receipts/rec_001/download",
  "doctor_email": "medico@clinic.com",
  "sent_at": "2025-02-10T10:35:00Z",
  "metadata": {
    "customer_name": "Paciente João",
    "amount": 500.00
  }
}
```

## 6. Database: email_logs (log de envios)

```json
{
  "id": 1,
  "account_id": "account_123abc",
  "receipt_id": "rec_001",
  "doctor_email": "medico@clinic.com",
  "status": "sent",
  "error_message": null,
  "created_at": "2025-02-10T10:35:00Z",
  "updated_at": "2025-02-10T10:35:00Z"
}
```

Com erro:

```json
{
  "id": 2,
  "account_id": "account_123abc",
  "receipt_id": "rec_002",
  "doctor_email": "invalido@invalid",
  "status": "failed",
  "error_message": "SMTP authentication failed",
  "created_at": "2025-02-10T10:40:00Z",
  "updated_at": "2025-02-10T10:40:05Z"
}
```

## 7. .env Configuration

```env
# Conta Azul
CONTA_AZUL_CLIENT_ID=abc123xyz
CONTA_AZUL_CLIENT_SECRET=secret123xyz
CONTA_AZUL_REDIRECT_URI=https://payflow.seu-dominio.com/api/oauth/callback
CONTA_AZUL_API_BASE_URL=https://api.contaazul.com
CONTA_AZUL_AUTH_URL=https://accounts.contaazul.com/oauth/authorize
CONTA_AZUL_TOKEN_URL=https://accounts.contaazul.com/oauth/token

# Segurança
MASTER_KEY=base64_encoded_32_bytes_here
JWT_SECRET=your_jwt_secret_here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_app_password
SMTP_FROM=seu_email@gmail.com
SMTP_REPLY_TO=seu_email@gmail.com
SMTP_USE_TLS=true

# Polling
POLLING_INTERVAL_SECONDS=300
POLLING_INITIAL_LOOKBACK_DAYS=30

# API
API_HOST=0.0.0.0
API_PORT=8000
API_LOG_LEVEL=info

# Database
DATABASE_URL=sqlite:///./data/payflow.db
DATABASE_ECHO=false

# Cloudflare Tunnel
CLOUDFLARE_TUNNEL_TOKEN=your_tunnel_token_here

# Fallback Médicos
DOCTORS_FALLBACK_JSON={"João Silva": "joao@doctors.com", "Maria Santos": "maria@doctors.com"}

# Projeto
PROJECT_NAME=PayFlow Automation
PROJECT_VERSION=1.0.0
```

## 8. Email Template (Recibo)

### Subject
```
Recibo de Pagamento - João Silva
```

### Body (Plain Text)
```
Prezado(a),

Segue anexado o recibo de pagamento para o cliente/paciente:

Cliente: João Silva
Valor: R$ 500,00
Data: 2025-02-10

Qualquer dúvida, favor entrar em contato.

Atenciosamente,
Sistema PayFlow
```

### Attachment
- **Filename**: `recibo_Joao_Silva.pdf`
- **Content-Type**: `application/pdf`
- **Content**: Binary PDF bytes

## 9. OAuth Flow URLs

### Authorization URL (gerada)

```
https://accounts.contaazul.com/oauth/authorize?
  client_id=abc123xyz&
  redirect_uri=https://payflow.seu-dominio.com/api/oauth/callback&
  response_type=code&
  state=random_csrf_token&
  scope=accounts.read+installments.read+receipts.read
```

### Callback URL (usuário é redirecionado)

```
https://payflow.seu-dominio.com/api/oauth/callback?
  code=auth_code_123&
  state=random_csrf_token
```

## 10. Rate Limit Headers

Request feito:

```
GET /v1/installments HTTP/1.1
Authorization: Bearer eyJhbGc...
```

Response headers:

```
HTTP/1.1 200 OK
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 599
X-RateLimit-Reset: 1612962045
Content-Type: application/json
```

Se limite atingido:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Remaining: 0
```

PayFlow automáticamente faz backoff exponencial e tenta novamente.

---

**Nota**: Todos os tokens e secrets aqui são fictícios. Use valores reais em produção!

