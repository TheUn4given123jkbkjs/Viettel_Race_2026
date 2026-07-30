@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal enabledelayedexpansion
title Viettel Race 2026 - Groq Model Isolation Launcher V1.0

echo ==============================================================================
echo   GROQ MODEL ISOLATION LAUNCHER V1.0 - Viettel AI Race 2026
echo   Phan lap luong chay chuyen trac cho tung Model (Tuk chinh so luong Workers)
echo ==============================================================================

echo.
echo [BUOC 1] Quet suc khoe CHI GROQ API Keys va cap nhat .env
echo ==============================================================================
python custom_scripts\refresh_keys.py --provider groq

echo.
echo [BUOC 2] Cau hinh thong tin sinh du lieu
echo ==============================================================================
set "MEMBER=V4_test"
set /p MEMBER="> Nhap ma thanh vien/ten ngan (Mac dinh: V4_test): "
if "%MEMBER%"=="" set "MEMBER=V4_test"

set "NUM_SAMPLES=2000"
set /p NUM_SAMPLES="> Nhap tong so luong mau can sinh (Mac dinh: 2000): "
if "%NUM_SAMPLES%"=="" set "NUM_SAMPLES=2000"

echo.
echo   [CHON CHE DO PHAN LAP MODEL]:
echo   1. Dan Llama 3.3 70B Versatile  (Chat luong cao - Pacing 12.0s)
echo   2. Dan Llama 3.1 8B Instant     (Nhan ban toc do - Pacing 2.0s)
echo   3. Dan Qwen 3.6 27B             (Suy luan logic  - Pacing 8.0s)
echo   4. BAT DONG THOI CA 3 DAN SONG SONG (Golden Ratio) [MAC DINH]
echo.
set "MODE_OPT=4"
set /p MODE_OPT="> Chon che do (1-4) [Mac dinh: 4]: "
if "%MODE_OPT%"=="" set "MODE_OPT=4"

set "BG_OPT=n"
set /p BG_OPT="> Chay ngam khong hien cua so CMD? (y/n) [Mac dinh: n]: "
set "BG_FLAG="
if /i "%BG_OPT%"=="y" set "BG_FLAG=--background"

echo.
echo ==============================================================================
echo   [TUY CHINH SO WORKERS CHO TUNG MODEL]
echo ==============================================================================

set "WORKERS_70B=4"
set "WORKERS_8B=3"
set "WORKERS_QWEN=1"

if "%MODE_OPT%"=="1" (
    set /p WORKERS_70B="> Nhap so worker cho Llama 70B [Mac dinh: 4]: "
    if "!WORKERS_70B!"=="" set "WORKERS_70B=4"
    echo.
    echo [BUOC 3] Khoi chay Dan Llama 3.3 70B (!WORKERS_70B! Workers)...
    python custom_scripts\groq_runner.py --member "%MEMBER%" --num_samples %NUM_SAMPLES% --workers !WORKERS_70B! --model "llama-3.3-70b-versatile" %BG_FLAG%
) else if "%MODE_OPT%"=="2" (
    set /p WORKERS_8B="> Nhap so worker cho Llama 8B [Mac dinh: 3]: "
    if "!WORKERS_8B!"=="" set "WORKERS_8B=3"
    echo.
    echo [BUOC 3] Khoi chay Dan Llama 3.1 8B (!WORKERS_8B! Workers)...
    python custom_scripts\groq_runner.py --member "%MEMBER%" --num_samples %NUM_SAMPLES% --workers !WORKERS_8B! --model "llama-3.1-8b-instant" %BG_FLAG%
) else if "%MODE_OPT%"=="3" (
    set /p WORKERS_QWEN="> Nhap so worker cho Qwen 27B [Mac dinh: 1]: "
    if "!WORKERS_QWEN!"=="" set "WORKERS_QWEN=1"
    echo.
    echo [BUOC 3] Khoi chay Dan Qwen 3.6 27B (!WORKERS_QWEN! Worker)...
    python custom_scripts\groq_runner.py --member "%MEMBER%" --num_samples %NUM_SAMPLES% --workers !WORKERS_QWEN! --model "qwen/qwen3.6-27b" %BG_FLAG%
) else (
    set /p WORKERS_70B="> Nhap so worker cho Llama 70B [Mac dinh: 4]: "
    if "!WORKERS_70B!"=="" set "WORKERS_70B=4"
    set /p WORKERS_8B="> Nhap so worker cho Llama 8B [Mac dinh: 3]: "
    if "!WORKERS_8B!"=="" set "WORKERS_8B=3"
    set /p WORKERS_QWEN="> Nhap so worker cho Qwen 27B [Mac dinh: 1]: "
    if "!WORKERS_QWEN!"=="" set "WORKERS_QWEN=1"
    echo.
    echo [BUOC 3] Khoi chay DONG THOI CA 3 DAN MODEL ISOLATED...
    echo   -> Dan 1: Llama 3.3 70B (!WORKERS_70B! Workers)...
    python custom_scripts\groq_runner.py --member "%MEMBER%" --num_samples %NUM_SAMPLES% --workers !WORKERS_70B! --model "llama-3.3-70b-versatile" %BG_FLAG%
    echo   -> Dan 2: Llama 3.1 8B (!WORKERS_8B! Workers)...
    python custom_scripts\groq_runner.py --member "%MEMBER%" --num_samples %NUM_SAMPLES% --workers !WORKERS_8B! --model "llama-3.1-8b-instant" %BG_FLAG%
    echo   -> Dan 3: Qwen 3.6 27B (!WORKERS_QWEN! Worker)...
    python custom_scripts\groq_runner.py --member "%MEMBER%" --num_samples %NUM_SAMPLES% --workers !WORKERS_QWEN! --model "qwen/qwen3.6-27b" %BG_FLAG%
)

echo.
pause
