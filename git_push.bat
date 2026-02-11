@echo off
REM Script para fazer commit e push do projeto PayFlow

echo.
echo ========================================
echo   PayFlow v1.0.0 - Commit e Push
echo ========================================
echo.

cd /d C:\Projeto\ctrls-payflow-v2

echo [1/4] Verificando status do Git...
git status

echo.
echo [2/4] Verificando commits...
git log --oneline -1

echo.
echo [3/4] Configurando branch main...
git branch -M main

echo.
echo [4/4] Fazendo push para GitHub...
git push -u origin main

echo.
echo ========================================
echo   Status Final
echo ========================================
echo.

git remote -v

echo.
echo Verificando última push...
git log -1 --format="Commit: %h - %s"

echo.
echo ✅ Commit e Push Concluído!
echo.
pause

