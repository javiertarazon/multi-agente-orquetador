@echo off
echo ===================================
echo Multi-Agente Orquestado - Setup MCP
echo ===================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instala Python 3.11+ primero.
    pause
    exit /b 1
)

REM Create virtual environment
echo [1/4] Creando entorno virtual...
python -m venv .venv
call .venv\Scripts\activate.bat

REM Install dependencies
echo [2/4] Instalando dependencias...
pip install -e ".[mcp]"

REM Setup database
echo [3/4] Configurando base de datos...
if not exist "data" mkdir data
if not exist "data\plans" mkdir data\plans

REM Copy env file
echo [4/4] Configurando variables de entorno...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env
        echo Archivo .env creado desde .env.example
        echo IMPORTANTE: Edita .env con tus API keys
    )
)

echo.
echo ===================================
echo Setup completado!
echo.
echo Para iniciar el servidor MCP:
echo   .venv\Scripts\activate
echo   python -m orchestrator.interfaces.mcp.server
echo.
echo Para ejecutar tests:
echo   pytest tests/ -v
echo ===================================
pause
