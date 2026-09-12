@echo off
REM Sobe SO o frontend (Next.js) apontando para o backend de producao (Render).
REM O backend nao roda localmente aqui -- ele vive no Render e a DATABASE_URL
REM do Supabase esta la. Se quiser rodar o stack completo local (raro), use
REM o iniciar-completo.bat (backend + frontend).
cd /d "%~dp0"

if not exist "frontend\node_modules" (
    echo [AVISO] frontend\node_modules nao encontrado. Rode primeiro:
    echo         cd frontend ^&^& npm install
    pause
    exit /b 1
)

echo Subindo o frontend (Next.js) na porta 3000...
echo Backend: apontando para https://whodados-backend.onrender.com (producao)
echo.
start "WhoDados - Frontend" cmd /k "cd frontend && npm run dev"
echo.
echo Abra http://localhost:3000 quando aparecer 'Ready' na janela do frontend.
echo (Primeira requisicao pode demorar ~50s -- Render free acorda o backend.)
echo Para parar, feche a janela do frontend.
pause
