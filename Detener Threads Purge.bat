@echo off
setlocal EnableExtensions
title Detener Threads Purge
echo.
echo    Deteniendo Threads Purge...
for %%P in (8000 3000) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":%%P  *[^ ]*  *LISTENING"') do (
    taskkill /PID %%I /T /F >nul 2>&1
  )
)
echo    Listo, Threads Purge esta cerrado.
timeout /t 2 /nobreak >nul
