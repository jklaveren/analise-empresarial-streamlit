@echo off
REM =================================================================
REM setup.bat - Configura o WhoDados numa maquina nova (rodar UMA vez).
REM Cria a venv, instala as dependencias do backend e do frontend e
REM prepara os arquivos .env. Depois disso, use iniciar.bat no dia a dia.
REM =================================================================
cd /d "%~dp0"
echo ==================================================
echo   WhoDados - Setup da maquina (rodar uma vez)
echo ==================================================
echo.

REM --- 1. Python / virtualenv ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH. Instale o Python 3.11+ e rode de novo.
    pause
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    echo [1/4] .venv ja existe, pulando criacao.
) else (
    echo [1/4] Criando virtualenv .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar a venv.
        pause
        exit /b 1
    )
)

echo [2/4] Instalando dependencias do backend ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias do backend.
    pause
    exit /b 1
)

REM --- 3. Frontend ---
echo [3/4] Instalando dependencias do frontend (npm install) ...
where npm >nul 2>nul
if errorlevel 1 (
    echo [AVISO] npm nao encontrado. Instale o Node.js e rode 'npm install' na pasta frontend manualmente.
) else (
    pushd frontend
    call npm install
    popd
)

REM --- 4. Arquivos .env ---
echo [4/4] Preparando arquivos .env ...
if exist "backend\.env" (
    echo       backend\.env ja existe, mantendo.
) else (
    copy /y "backend\.env.example" "backend\.env" >nul
    echo       backend\.env criado a partir do exemplo. PREENCHA a DATABASE_URL.
)
if exist "frontend\.env.local" (
    echo       frontend\.env.local ja existe, mantendo.
) else (
    copy /y "frontend\.env.example" "frontend\.env.local" >nul
    echo       frontend\.env.local criado ^(NEXT_PUBLIC_API_URL=http://localhost:8000^).
)

echo.
echo ==================================================
echo   Setup concluido.
echo.
echo   FALTA VOCE: abrir backend\.env e preencher:
echo     - DATABASE_URL  (connection string do Supabase)
echo     - SECRET_KEY    (qualquer texto aleatorio)
echo.
echo   Depois disso, rode iniciar.bat.
echo ==================================================
pause
