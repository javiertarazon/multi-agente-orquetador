@echo off
:restart
echo [%date% %time%] MCP Server starting...
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python -m orchestrator.interfaces.mcp.server
echo [%date% %time%] MCP Server exited with code %ERRORLEVEL%
echo Restarting in 2 seconds...
timeout /t 2 >nul
goto restart
