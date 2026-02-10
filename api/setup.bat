@echo off
REM Script para setup do ambiente de desenvolvimento

echo.
echo ===== Setup do Ambiente PayFlow API =====
echo.

REM 1. Criar venv
echo [1/4] Criando virtual environment...
python -m venv .venv

REM 2. Ativar venv
echo [2/4] Ativando virtual environment...
call .venv\Scripts\activate.bat

REM 3. Atualizar pip
echo [3/4] Atualizando pip...
python -m pip install --upgrade pip

REM 4. Instalar dependências
echo [4/4] Instalando dependências...
pip install -r requirements.txt

echo.
echo ===== Setup Concluído! =====
echo.
echo Para ativar o venv novamente, use:
echo   .venv\Scripts\activate.bat
echo.
echo Para rodar a API:
echo   uvicorn app.main:app --reload
echo.
echo Para rodar os testes:
echo   pytest tests/ -v
echo.

pause

