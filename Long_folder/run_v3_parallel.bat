@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal enabledelayedexpansion
title Viettel Race 2026 - Master Parallel Data Generator V6.0

echo ==============================================================================
echo  BUOC 1: QUET SUC KHOE API KEYS VA CAP NHAT .ENV
echo ==============================================================================
python custom_scripts\refresh_keys.py

echo.
echo ==============================================================================
echo  BUOC 2: CAU HINH THONG TIN SINH DU LIEU
echo ==============================================================================
set "MEMBER=C"
set /p MEMBER="> Nhap ma thanh vien / ten thu muc dau ra [Mac dinh: C]: "
if "%MEMBER%"=="" set "MEMBER=C"

set "PROVIDER=auto"
set /p PROVIDER="> Nhap nha cung cap AI (auto / gemini / groq / sambanova) [Mac dinh: auto]: "
if "%PROVIDER%"=="" set "PROVIDER=auto"

set "NUM_SAMPLES=2000"
set /p NUM_SAMPLES="> Nhap tong so luong mau can sinh [Mac dinh: 2000]: "
if "%NUM_SAMPLES%"=="" set "NUM_SAMPLES=2000"

echo.
echo  [THONG TIN CAU HINH DA CHON]:
echo   - Thu muc dau ra : sample_%MEMBER%
echo   - Nha cung cap   : %PROVIDER%
echo   - Tong so mau    : %NUM_SAMPLES%
echo.

echo ==============================================================================
echo  BUOC 3: TU DONG TINH WORKER TOI UU VA KHOI CHAY DAN WORKERS SONG SONG
echo ==============================================================================
python custom_scripts\auto_adjust_workers.py --member "%MEMBER%" --provider "%PROVIDER%" --num_samples %NUM_SAMPLES%

echo.
pause
