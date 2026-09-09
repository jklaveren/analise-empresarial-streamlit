@echo off
REM Inicia o WhoDados localmente: abre o backend (FastAPI) e o frontend (Next.js)
REM cada um em sua propria janela, para testar antes de comitar no git.
cd /d "%~dp0"

echo Iniciando backend (FastAPI) na porta 8000...
start "WhoDados - Backend" cmd /k "uvicorn backend.main:app --reload --port 8000"

echo Iniciando frontend (Next.js) na porta 3000...
start "WhoDados - Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo As duas janelas que abriram mostram os logs dos servidores.
echo Para parar, basta fechar essas janelas.
pause
