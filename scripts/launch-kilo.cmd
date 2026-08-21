@echo off
setlocal
cd /d "%~dp0.."
title Kilo CLI - Multi Agente Orquestado
call "%APPDATA%\npm\kilo.cmd" %*
endlocal
