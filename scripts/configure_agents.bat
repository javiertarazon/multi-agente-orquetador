@echo off
echo ===================================
echo Configurando Agentes para MCP
echo ===================================
echo.

set MCP_SERVER_PATH=%~dp0..\src\orchestrator\interfaces\mcp\server.py
set VENV_PYTHON=%~dp0..\..\.venv\Scripts\python.exe

REM Configure OpenCode
echo [1/4] Configurando OpenCode...
if not exist "%USERPROFILE%\.config\opencode" mkdir "%USERPROFILE%\.config\opencode"

REM Configure Kilo (VS Code extension)
echo [2/4] Verificando Kilo...
where kilo >nul 2>&1
if errorlevel 1 (
    echo WARN: Kilo no encontrado en PATH
    echo Instala la extension de VS Code: Kilo Code
) else (
    echo Kilo encontrado: 
    where kilo
)

REM Configure Cline
echo [3/4] Verificando Cline...
where cline >nul 2>&1
if errorlevel 1 (
    echo WARN: Cline no encontrado en PATH
    echo Instala: npm install -g @anthropic-ai/cline
) else (
    echo Cline encontrado:
    where cline
)

REM Configure Hermes
echo [4/4] Verificando Hermes...
where hermes >nul 2>&1
if errorlevel 1 (
    echo WARN: Hermes no encontrado en PATH
    echo Verifica: D:\datos jt7\proyectos\hermes-agent\venv311\Scripts\hermes.exe
) else (
    echo Hermes encontrado:
    where hermes
)

echo.
echo ===================================
echo Configuracion completada!
echo.
echo Variables de entorno configuradas en .env:
echo   MAOQ_KILO_BIN - Ruta a Kilo CLI
echo   MAOQ_CLINE_BIN - Ruta a Cline CLI  
echo   MAOQ_HERMES_BIN - Ruta a Hermes CLI
echo   MAOQ_MAX_WORKERS - Workers paralelos (default: 3)
echo   MAOQ_HARNESS_MAX_TIMEOUT - Timeout maximo por tarea (default: 3600s)
echo ===================================
pause
