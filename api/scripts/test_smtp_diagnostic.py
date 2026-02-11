"""
Teste de diagnóstico SMTP - Valida conexão e autenticação.
"""

import sys
import smtplib
import ssl
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings

def test_smtp_connection():
    """Testa conexão SMTP com diferentes métodos."""
    print("\n" + "=" * 80)
    print("🔍 DIAGNÓSTICO SMTP")
    print("=" * 80 + "\n")

    settings = get_settings()

    print("📋 Configuração:")
    print(f"   Host: {settings.SMTP_HOST}")
    print(f"   Port: {settings.SMTP_PORT}")
    print(f"   User: {settings.SMTP_USER}")
    print(f"   Password: {'*' * len(settings.SMTP_PASSWORD)}")
    print(f"   Use SSL: {settings.SMTP_USE_SSL}")
    print(f"   Use TLS: {settings.SMTP_USE_TLS}")
    print()

    # Teste 1: Conexão básica
    print("🔌 Teste 1: Conectar ao servidor...")
    try:
        if settings.SMTP_USE_SSL:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=10,
                context=context
            )
            print(f"✅ Conectado via SSL na porta {settings.SMTP_PORT}")
        else:
            server = smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=10
            )
            print(f"✅ Conectado na porta {settings.SMTP_PORT}")

            if settings.SMTP_USE_TLS:
                print("🔒 Iniciando STARTTLS...")
                server.starttls()
                print("✅ STARTTLS OK")

        # Ver comandos suportados
        print("\n📝 Comandos SMTP suportados:")
        print(f"   {server.ehlo_resp.decode('utf-8', errors='ignore')}")

        # Teste 2: Autenticação
        print("\n🔐 Teste 2: Autenticar...")
        try:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            print("✅ Autenticação OK!")

            # Teste 3: Verificar sender
            print("\n📧 Teste 3: Verificar sender...")
            try:
                code, msg = server.verify(settings.SMTP_FROM)
                print(f"✅ Sender válido: {code} - {msg}")
            except Exception as e:
                print(f"⚠️  VRFY não suportado ou sender não verificado: {e}")

            server.quit()
            print("\n" + "=" * 80)
            print("✅ TODOS OS TESTES PASSARAM!")
            print("=" * 80)
            return True

        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Erro de autenticação: {e}")
            print("\n🔍 Detalhes do erro:")
            print(f"   Código: {e.smtp_code}")
            print(f"   Mensagem: {e.smtp_error.decode('utf-8', errors='ignore')}")

            print("\n💡 Possíveis soluções:")
            print("   1. Verificar usuário e senha no .env")
            print("   2. Alguns servidores exigem email completo como usuário")
            print("   3. Verificar se conta precisa habilitar 'acesso menos seguro'")
            print("   4. Verificar se IP não está bloqueado")

            server.quit()
            return False

    except smtplib.SMTPConnectError as e:
        print(f"❌ Erro ao conectar: {e}")
        print("\n💡 Verificar:")
        print("   - Firewall bloqueando porta")
        print("   - Host incorreto")
        return False

    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_smtp_connection()
    sys.exit(0 if success else 1)

