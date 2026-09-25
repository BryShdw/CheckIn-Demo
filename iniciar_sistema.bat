@echo off
cd /d "%~dp0"
title Sistema de Check-in DACER - Brother QL-800

echo ========================================================
echo   Iniciando Sistema de Check-in Kiosko DACER
echo   Brother QL-800 (Rollo DK-1208 38mm x 90.3mm)
echo   Kiosko de Escaneo: http://localhost:5000
echo   Panel de Admin:    http://localhost:5000/admin
echo ========================================================

:: Lanzamiento automático en Modo Kiosko a Pantalla Completa (Sin interfaz de navegador)
start "" /b cmd /c "timeout /t 3 /nobreak >nul & (if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" ("%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --kiosk "http://localhost:5000" --edge-kiosk-type=fullscreen --no-first-run) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" ("%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --kiosk "http://localhost:5000" --edge-kiosk-type=fullscreen --no-first-run) else if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" ("%ProgramFiles%\Google\Chrome\Application\chrome.exe" --kiosk "http://localhost:5000" --no-first-run) else (start http://localhost:5000))"

if exist .\venv\Scripts\python.exe (
    .\venv\Scripts\python.exe app.py
) else (
    python app.py
)
pause
