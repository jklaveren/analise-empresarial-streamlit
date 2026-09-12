@echo off
REM Sobe backend (FastAPI) + frontend (Next.js) localmente. So use se estiver
REM MEXENDO NO BACKEND -- precisa de .venv, deps instaladas e DATABASE_URL
REM preenchida no backend\.env. Para o uso normal (mexer so no frontend),
REM use iniciar.bat.
cd /d "%~dp0"

if not exist "backend\.env" (
    echo [AVISO] backend\.env nao encontrado. Backend nao vai conectar no Supabase.
    echo         Preencha DATABASE_URL em backend\.env antes de rodar.
    echo.
)
if not exist "frontend\node_modules" (
    echo [AVISO] frontend\node_modules nao encontrado. Rode 'npm install' na pasta frontend antes.
    echo.
)

if exist ".venv\Scripts\activate.bat" (
    set "ATIVAR_VENV=call .venv\Scripts\activate.bat && "
) else (
    echo [AVISO] .venv nao encontrada. Usando Python do PATH global.
    echo         Se der 'uvicorn nao reconhecido', crie a venv:
    echo         python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r backend\requirements.txt
    echo.
    set "ATIVAR_VENV="
)

echo Iniciando backend (FastAPI) na porta 8000...
start "WhoDados - Backend" cmd /k "%ATIVAR_VENV%uvicorn backend.main:app --reload --port 8000"

echo Iniciando frontend (Next.js) na porta 3000...
start "WhoDados - Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo.
pause
