@echo off
REM Inicia o WhoDados localmente: backend (FastAPI) + frontend (Next.js),
REM cada um em sua propria janela, para testar antes de comitar no git.
cd /d "%~dp0"

REM --- Avisos de setup (clone novo nao tem .env nem node_modules) ---
if not exist "backend\.env" (
    echo [AVISO] backend\.env nao encontrado. O backend nao vai conectar no Supabase.
    echo         Crie a partir de backend\.env.example e preencha a DATABASE_URL.
    echo.
)
if not exist "frontend\node_modules" (
    echo [AVISO] frontend\node_modules nao encontrado. Rode 'npm install' na pasta frontend antes.
    echo.
)

REM --- Ativa a virtualenv (.venv) se existir, para o uvicorn ser encontrado ---
if exist ".venv\Scripts\activate.bat" (
    set "ATIVAR_VENV=call .venv\Scripts\activate.bat && "
) else (
    echo [AVISO] .venv nao encontrada. Usando o Python do PATH global.
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
echo As duas janelas que abriram mostram os logs dos servidores.
echo Para parar, basta fechar essas janelas.
pause
