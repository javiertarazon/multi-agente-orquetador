@echo off
setlocal
cd /d "%~dp0.."
title Cline CLI - Multi Agente Orquestado
call "%APPDATA%\npm\cline.cmd" %*
endlocal
