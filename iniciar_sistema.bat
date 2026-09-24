@echo off
cd /d "%~dp0"
title Sistema de Check-in - Brother QL-800 (QR + Facial)
echo ========================================================
echo   Iniciando Sistema de Check-in con Brother QL-800
echo   Modalidad: QR + Reconocimiento Facial
echo   Rollo: DK-1208 (38mm x 90.3mm)
echo   Kiosko de Escaneo: http://localhost:5000
echo   Panel de Admin:    http://localhost:5000/admin
echo ========================================================
timeout /t 2 /nobreak >nul
start http://localhost:5000
if exist .\venv\Scripts\python.exe (
    .\venv\Scripts\python.exe app.py
) else (
    python app.py
)
pause
