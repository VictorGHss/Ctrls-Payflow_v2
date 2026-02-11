#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de inicialização rápida do PayFlow
Configura SQLite, migrations e tudo para rodar localmente
"""

import os
import subprocess
import sys
from pathlib import Path

# Cores para output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(msg):
    print(f"\n{BOLD}{GREEN}{'='*60}{RESET}")
    print(f"{BOLD}{GREEN}{msg:^60}{RESET}")
    print(f"{BOLD}{GREEN}{'='*60}{RESET}\n")


def print_step(step_num, msg):
    print(f"{BOLD}{YELLOW}[{step_num}]{RESET} {msg}")


def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")


def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")


def print_info(msg):
    print(f"ℹ️  {msg}")


def run_command(cmd, description, show_output=False):
    """Executa um comando e trata erros"""
    try:
        print_info(f"Executando: {cmd}")
        result = subprocess.run(
            cmd, shell=True, check=False, capture_output=True, text=True
        )

        if show_output and result.stdout:
            print(result.stdout)

        if result.returncode != 0:
            if result.stderr:
                print_error(f"{description}: {result.stderr[:200]}")
            return False

        print_success(description)
        return True
    except Exception as e:
        print_error(f"{description}: {str(e)[:200]}")
        return False


def setup_venv():
    """Cria e configura virtual environment."""
    print_step(2, "Verificando Virtual Environment")
    venv_dir = Path(".venv")

    if not venv_dir.exists():
        print_info("Criando virtual environment...")
        if not run_command("python -m venv .venv", "Virtual environment criado"):
            sys.exit(1)
    else:
        print_success("Virtual environment já existe")


def install_dependencies():
    """Instala dependências do requirements.txt."""
    print_step(3, "Instalando dependências")

    # No Windows, usar python -m pip é mais confiável
    pip_cmd = "python -m pip" if sys.platform == "win32" else ".venv/bin/pip"

    if not run_command(f"{pip_cmd} install --upgrade pip", "Pip atualizado"):
        print_error("Não foi possível atualizar pip, continuando...")

    if not run_command(
        f"{pip_cmd} install -r requirements.txt",
        "Dependências instaladas",
        show_output=True,
    ):
        print_error("Erro ao instalar dependências")
        sys.exit(1)


def setup_env_file():
    """Cria arquivo .env se não existir."""
    print_step(4, "Configurando variáveis de ambiente")
    env_file = Path(".env")
    env_example = Path(".env.example")

    if not env_file.exists():
        if env_example.exists():
            import shutil

            shutil.copy(env_example, env_file)
            print_success(".env criado a partir de .env.example")
            print_info("⚠️  IMPORTANTE: Edite .env com suas configurações:")
            print("   - CONTA_AZUL_CLIENT_ID")
            print("   - CONTA_AZUL_CLIENT_SECRET")
            print("   - CONTA_AZUL_REDIRECT_URI")
            print("   - MASTER_KEY (gerar: python scripts/generate_key.py)")
            print("   - SMTP_* (configurações de email)")
        else:
            print_error(".env.example não encontrado")
    else:
        print_success(".env já existe")


def init_database():
    """Inicializa banco de dados SQLite."""
    print_step(7, "Inicializando banco de dados SQLite")
    try:
        from app.config import get_settings
        from app.database import Base, init_db

        settings = get_settings()
        print_info(f"Database: {settings.DATABASE_URL}")

        engine, SessionLocal = init_db(settings.DATABASE_URL)
        print_success("Database inicializado")

        # Criar tabelas
        Base.metadata.create_all(bind=engine)
        print_success("Tabelas criadas")

    except Exception as e:
        print_error(f"Erro ao inicializar database: {e}")
        sys.exit(1)


def main():
    print_header("PayFlow v1.0.0 - Inicialização Local")

    # Aviso para versões futuras (3.13 agora suportado pelas dependências atualizadas)
    if sys.version_info >= (3, 14):
        print_error("Python 3.14+ pode nao ser suportado pelas dependencias atuais.")
        print_info("Use Python 3.10–3.13 para criar o venv e instalar dependencias.")
        sys.exit(1)

    # Verificar se está no diretório correto
    api_dir = Path(__file__).parent
    if not (api_dir / "app").exists():
        print_error("Execute este script no diretório 'api'")
        sys.exit(1)

    os.chdir(api_dir)

    # Passo 1: Verificar Python
    print_step(1, "Verificando Python")
    if not run_command("python --version", "Python encontrado"):
        sys.exit(1)

    # Passos 2-4: Setup básico
    setup_venv()
    install_dependencies()
    setup_env_file()

    # Passo 5: Criar diretório de dados
    print_step(5, "Criando diretório de dados")
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    print_success(f"Diretório {data_dir} criado/verificado")

    # Passo 6: Verificar MASTER_KEY
    print_step(6, "Verificando MASTER_KEY")
    try:
        from app.config import get_settings

        settings = get_settings()
        if settings.MASTER_KEY:
            print_success("MASTER_KEY encontrada no .env")
        else:
            print_error("MASTER_KEY não configurada")
            print_info("Gere uma nova chave com:")
            print("   python scripts/generate_key.py")
    except Exception as e:
        print_error(f"Erro ao carregar config: {e}")
        print_info("Certifique-se de que .env está configurado corretamente")

    # Passo 7: Inicializar banco de dados
    init_database()

    # Passo 8: Rodar testes
    print_step(8, "Rodando testes")
    if run_command("python -m pytest tests/ -v --tb=short", "Testes executados"):
        print_success("Todos os testes passaram!")
    else:
        print_error("Alguns testes falharam (mas você pode continuar)")

    # Resumo final
    print_header("✅ Inicialização Completa!")

    print(f"{BOLD}PayFlow está pronto para rodar!{RESET}\n")

    print(f"{BOLD}Para rodar a API local:{RESET}")
    if sys.platform == "win32":
        print("  .venv\\Scripts\\activate")
    else:
        print("  source .venv/bin/activate")
    print("  uvicorn app.main:app --reload")

    print(f"\n{BOLD}Para rodar o Worker:{RESET}")
    if sys.platform == "win32":
        print("  .venv\\Scripts\\activate")
    else:
        print("  source .venv/bin/activate")
    print("  python -m app.worker.main")

    print(f"\n{BOLD}Documentação:{RESET}")
    print("  - README.md: Visão geral")
    print("  - QUICKSTART.md: Início rápido")
    print("  - DEPLOY.md: Deploy em produção")
    print("  - SECURITY_AUDIT.md: Análise de segurança")

    print(f"\n{BOLD}URLs Úteis:{RESET}")
    print("  - API: http://localhost:8000")
    print("  - Swagger: http://localhost:8000/docs")
    print("  - ReDoc: http://localhost:8000/redoc")

    print(f"\n{BOLD}Banco de Dados:{RESET}")
    print("  - SQLite: data/payflow.db")
    print("  - Inspecionar: sqlite3 data/payflow.db")

    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}🚀 Pronto para começar!{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")


if __name__ == "__main__":
    main()
