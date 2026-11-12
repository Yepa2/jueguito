@echo off
title Discretizando el Tiempo Continuo
cd /d "%~dp0"

echo ===================================================
echo   Iniciando Discretizando el Tiempo Continuo...
echo ===================================================

where python >nul 2>nul
if %errorlevel% equ 0 (
    python run.py
    goto end
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    py run.py
    goto end
)

echo [ERROR] No se encontro Python instalado en el sistema.
echo Por favor instala Python desde https://www.python.org/downloads/
echo Asegurate de marcar la casilla "Add python.exe to PATH" durante la instalacion.
echo.
pause
exit /b 1

:end
pause
