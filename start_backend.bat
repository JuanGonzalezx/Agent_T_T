@echo off
REM Script para iniciar el servidor backend de WhatsApp Messaging API

echo.
echo ========================================================================
echo   WhatsApp Messaging API - Backend Server
echo ========================================================================
echo.

REM Verificar que estemos en el directorio correcto
if not exist "backend\app.py" (
    echo ERROR: No se encuentra backend\app.py
    echo Por favor ejecuta este script desde la raiz del proyecto
    pause
    exit /b 1
)

REM Verificar que exista el archivo .env
if not exist ".env" (
    echo.
    echo ADVERTENCIA: No se encontro el archivo .env
    echo.
    echo Por favor:
    echo   1. Copia backend\.env.example a .env
    echo   2. Configura tus credenciales de WhatsApp Business API
    echo.
    pause
)

REM Activar entorno virtual si existe
if exist ".venv\Scripts\activate.bat" (
    echo Activando entorno virtual...
    call .venv\Scripts\activate.bat
) else (
    echo.
    echo ADVERTENCIA: No se encontro el entorno virtual en .venv
    echo.
)

REM Cambiar al directorio backend
cd backend

REM Iniciar el servidor
echo.
echo Iniciando servidor...
echo.
python app.py

pause
