"""
Teste isolado do serviço SMTP.

Valida:
1. Configuração SMTP
2. Validação de anexo PDF
3. Envio de email de teste

Uso:
    python scripts/test_smtp.py seu_email@gmail.com
"""

import sys
from pathlib import Path

# Adicionar path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.mailer import MailerService
from app.config import get_settings
from app.logging import setup_logging

logger = setup_logging(__name__)


def create_test_pdf() -> bytes:
    """Cria um PDF mínimo válido para teste."""
    # PDF mínimo válido
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Recibo de Teste) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF"""


def test_smtp(recipient_email: str):
    """Testa envio SMTP."""
    print("\n" + "=" * 80)
    print("📧 TESTE DE SMTP - MAILER SERVICE")
    print("=" * 80 + "\n")

    # 1. Carregar configuração
    settings = get_settings()

    print("✅ Configuração SMTP carregada:")
    print(f"   Host: {settings.SMTP_HOST}")
    print(f"   Port: {settings.SMTP_PORT}")
    print(f"   User: {settings.SMTP_USER}")
    print(f"   From: {settings.SMTP_FROM}")
    print(f"   TLS: {settings.SMTP_USE_TLS}")
    print(f"   Timeout: {settings.SMTP_TIMEOUT}s")
    print()

    # 2. Criar mailer
    try:
        mailer = MailerService()
        print("✅ MailerService inicializado\n")
    except Exception as e:
        print(f"❌ Erro ao inicializar MailerService: {e}")
        return False

    # 3. Criar PDF de teste
    print("📄 Criando PDF de teste...")
    pdf_content = create_test_pdf()
    print(f"✅ PDF criado: {len(pdf_content)} bytes\n")

    # 4. Enviar email de teste
    print(f"📤 Enviando email de teste para: {recipient_email}")
    print("   (isso pode levar alguns segundos...)\n")

    try:
        success = mailer.send_receipt_email(
            doctor_email=recipient_email,
            customer_name="João Silva (TESTE)",
            amount=1234.56,
            receipt_date="2026-02-11",
            pdf_content=pdf_content,
            pdf_filename="recibo_teste.pdf",
            reply_to=settings.SMTP_REPLY_TO or None,
        )

        if success:
            print("=" * 80)
            print("✅ EMAIL ENVIADO COM SUCESSO!")
            print("=" * 80)
            print()
            print("📬 Verifique:")
            print(f"   1. Caixa de entrada de: {recipient_email}")
            print("   2. Pasta de SPAM (caso não apareça)")
            print("   3. Anexo: recibo_teste.pdf deve estar presente")
            print()
            print("📧 Detalhes do email:")
            print(f"   De: {settings.SMTP_FROM}")
            print(f"   Para: {recipient_email}")
            print("   Assunto: Recibo de pagamento - João Silva (TESTE)")
            print("   Anexo: recibo_teste.pdf (teste de PDF)")
            print()
            return True
        else:
            print("=" * 80)
            print("❌ FALHA AO ENVIAR EMAIL")
            print("=" * 80)
            print()
            print("🔍 Possíveis causas:")
            print("   1. SMTP_PASSWORD incorreto (Gmail: use App Password!)")
            print("   2. Firewall bloqueando porta 587")
            print("   3. SMTP_HOST incorreto")
            print("   4. TLS não suportado")
            print()
            print("📝 Verificar logs acima para detalhes do erro")
            print()
            return False

    except Exception as e:
        print("=" * 80)
        print("❌ ERRO AO ENVIAR EMAIL")
        print("=" * 80)
        print()
        print(f"Erro: {e}")
        print()
        print("🔍 Troubleshooting:")
        print()
        print("   Gmail:")
        print("   1. Habilitar 2FA: myaccount.google.com/security")
        print("   2. Gerar App Password: myaccount.google.com/apppasswords")
        print("   3. Usar App Password (16 dígitos) no .env")
        print()
        print("   SendGrid:")
        print("   SMTP_USER=apikey (literal)")
        print("   SMTP_PASSWORD=SG.sua_api_key")
        print()
        print("   Outlook:")
        print("   SMTP_HOST=smtp.office365.com")
        print("   SMTP_PORT=587")
        print()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n❌ Uso: python scripts/test_smtp.py seu_email@gmail.com\n")
        sys.exit(1)

    recipient = sys.argv[1]

    # Validação básica de email
    if "@" not in recipient or "." not in recipient.split("@")[1]:
        print(f"\n❌ Email inválido: {recipient}\n")
        sys.exit(1)

    success = test_smtp(recipient)
    sys.exit(0 if success else 1)

