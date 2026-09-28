@echo off
setlocal EnableExtensions
title Threads Purge
cd /d "%~dp0"
set "ROOT=%~dp0"
set "LOGS=%ROOT%logs"
set "VPY=%ROOT%backend\.venv\Scripts\python.exe"
set "APP_URL=http://localhost:3000"
if not exist "%LOGS%" mkdir "%LOGS%"

echo.
echo    ==================================
echo            T H R E A D S   P U R G E
echo    ==================================
echo.

where curl.exe >nul 2>&1
if errorlevel 1 (
  echo    Necesitas Windows 10 version 1803 o mas nuevo, o Windows 11.
  goto fail
)

rem --- Ya esta corriendo? Solo abre la ventana.
curl.exe -s -o nul --max-time 2 http://127.0.0.1:8000/health
if errorlevel 1 goto setup
curl.exe -s -o nul --max-time 2 http://127.0.0.1:3000
if errorlevel 1 goto setup
echo    Threads Purge ya esta corriendo. Abriendo ventana...
goto open_app

:setup
rem --- Archivo de configuracion
if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo    Se creo el archivo .env - agrega ahi THREADS_APP_ID y THREADS_APP_SECRET.
  echo.
)

rem --- Backend: Python + dependencias, solo la primera vez
if exist "backend\.venv\.tp_ready" goto backend_ok
call :find_python
if errorlevel 1 goto fail
echo    [1/4] Instalando el servidor - solo la primera vez, espera unos minutos...
if not exist "%VPY%" %PY% -m venv "backend\.venv" >>"%LOGS%\setup.log" 2>&1
if not exist "%VPY%" goto fail_log
"%VPY%" -m pip install --upgrade pip >>"%LOGS%\setup.log" 2>&1
"%VPY%" -m pip install -r "backend\requirements.txt" >>"%LOGS%\setup.log" 2>&1
if errorlevel 1 goto fail_log
echo    [2/4] Instalando el modelo de imagenes CLIP - puede tardar 5 a 10 minutos...
set "ML_OK=1"
"%VPY%" -m pip install torch --index-url https://download.pytorch.org/whl/cpu >>"%LOGS%\setup.log" 2>&1
if errorlevel 1 set "ML_OK="
if defined ML_OK "%VPY%" -m pip install -r "backend\requirements-ml.txt" >>"%LOGS%\setup.log" 2>&1
if errorlevel 1 set "ML_OK="
if not defined ML_OK (
  echo    AVISO: no se pudo instalar CLIP. Se usara el modo basico de similitud.
  echo EMBEDDING_MODEL=debug-color-histogram>>".env"
)
if defined ML_OK (
  echo          Descargando el modelo...
  "%VPY%" "backend\scripts\prefetch_model.py" >>"%LOGS%\setup.log" 2>&1
  if errorlevel 1 echo    AVISO: el modelo se descargara en la primera busqueda.
)
echo ok>"backend\.venv\.tp_ready"
:backend_ok

rem --- Frontend: Node + compilar la interfaz, solo la primera vez
if exist "frontend\node_modules\.tp_ready" if exist "frontend\.next\BUILD_ID" goto frontend_ok
call :find_node
if errorlevel 1 goto fail
pushd "frontend"
if not exist "node_modules\.tp_ready" (
  echo    [3/4] Instalando la interfaz...
  call npm ci >>"%LOGS%\setup.log" 2>&1
  if errorlevel 1 ( popd & goto fail_log )
  echo ok>"node_modules\.tp_ready"
)
echo    [4/4] Compilando la interfaz...
call npm run build >>"%LOGS%\setup.log" 2>&1
if errorlevel 1 ( popd & goto fail_log )
popd
:frontend_ok

rem --- Acceso directo con icono dentro de la carpeta, solo la primera vez
if not exist "%ROOT%Abrir Threads Purge.lnk" powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%ROOT%Abrir Threads Purge.lnk'); $s.TargetPath='%ROOT%Threads Purge.bat'; $s.WorkingDirectory='%ROOT%'; $s.IconLocation='%ROOT%launcher\threads-purge.ico'; $s.WindowStyle=7; $s.Save()" >nul 2>&1

rem --- Arrancar servidores en ventanas minimizadas
echo    Iniciando Threads Purge...
curl.exe -s -o nul --max-time 2 http://127.0.0.1:8000/health
if errorlevel 1 start "Threads Purge - servidor (no cerrar)" /min /D "%ROOT%backend" cmd /c ""%VPY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "%LOGS%\backend.log" 2>&1"
curl.exe -s -o nul --max-time 2 http://127.0.0.1:3000
if errorlevel 1 start "Threads Purge - interfaz (no cerrar)" /min /D "%ROOT%frontend" cmd /c ""%ROOT%frontend\node_modules\.bin\next.cmd" start -H 127.0.0.1 -p 3000 > "%LOGS%\frontend.log" 2>&1"

set /a TRIES=0
:wait_loop
set /a TRIES+=1
curl.exe -s -o nul --max-time 2 http://127.0.0.1:8000/health
if errorlevel 1 goto wait_more
curl.exe -s -o nul --max-time 2 http://127.0.0.1:3000
if errorlevel 1 goto wait_more
goto open_app
:wait_more
if %TRIES% GEQ 90 goto fail_start
timeout /t 1 /nobreak >nul
goto wait_loop

:open_app
rem --- Abrir como app (ventana sin barra del navegador) con Edge o Chrome
set "PF86=%ProgramFiles(x86)%"
set "BROWSER="
if exist "%PF86%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%PF86%\Microsoft\Edge\Application\msedge.exe"
if not defined BROWSER if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not defined BROWSER if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "BROWSER=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if defined BROWSER (
  start "" "%BROWSER%" --app=%APP_URL% --window-size=1440,900
) else (
  start "" %APP_URL%
)
echo    Listo. Para cerrar Threads Purge usa "Detener Threads Purge.bat".
timeout /t 3 /nobreak >nul
exit /b 0

rem =====================================================================
:find_python
set "PY="
for %%V in (3.12 3.13 3.11 3.14) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=python"
)
if defined PY exit /b 0
echo    No encontre Python 3.11 o mas nuevo.
where winget >nul 2>&1
if errorlevel 1 goto python_manual
choice /C SN /M "   Quieres instalar Python 3.12 ahora"
if errorlevel 2 goto python_manual
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
echo.
echo    Python instalado. Cierra esta ventana y vuelve a abrir "Threads Purge.bat".
exit /b 1
:python_manual
echo    Instala Python 3.12 desde https://www.python.org/downloads/
echo    y marca la casilla "Add python.exe to PATH". Luego vuelve a abrir este archivo.
exit /b 1

:find_node
where node >nul 2>&1
if errorlevel 1 goto node_missing
node -e "process.exit(+process.versions.node.split('.')[0] >= 20 ? 0 : 1)" >nul 2>&1
if errorlevel 1 goto node_missing
exit /b 0
:node_missing
echo    No encontre Node.js 20 o mas nuevo.
where winget >nul 2>&1
if errorlevel 1 goto node_manual
choice /C SN /M "   Quieres instalar Node.js LTS ahora"
if errorlevel 2 goto node_manual
winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
echo.
echo    Node.js instalado. Cierra esta ventana y vuelve a abrir "Threads Purge.bat".
exit /b 1
:node_manual
echo    Instala Node.js LTS desde https://nodejs.org/ y vuelve a abrir este archivo.
exit /b 1

:fail_log
echo.
echo    Algo fallo durante la instalacion. Ultimas lineas de logs\setup.log:
echo    ------------------------------------------------------------------
powershell -NoProfile -Command "Get-Content -Tail 25 '%LOGS%\setup.log'"
goto fail

:fail_start
echo.
echo    Los servidores no respondieron a tiempo. Revisa logs\backend.log y logs\frontend.log
goto fail

:fail
echo.
pause
exit /b 1
