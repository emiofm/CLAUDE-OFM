@echo off
setlocal EnableExtensions
title Actualizar Threads Purge
cd /d "%~dp0"
echo.
echo    Actualizando Threads Purge...
call "%~dp0Detener Threads Purge.bat"
if exist ".git" (
  git pull
) else (
  echo    Esta carpeta no es un repositorio git: para actualizar, descarga el ZIP nuevo
  echo    y reemplaza los archivos. Tus datos en backend\data y tu archivo .env se conservan.
)
rem Forzar reinstalacion de dependencias y recompilar la interfaz
del /q "backend\.venv\.tp_ready" >nul 2>&1
del /q "frontend\node_modules\.tp_ready" >nul 2>&1
if exist "frontend\.next" rmdir /s /q "frontend\.next"
call "%~dp0Threads Purge.bat"
