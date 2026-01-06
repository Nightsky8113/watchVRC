@echo off
chcp 65001 > nul
echo ========================================
echo V睡録画ソフト - 依存パッケージのインストール
echo ========================================
echo.

REM Pythonコマンドを確認
where py >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto :install
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :install
)

echo [エラー] Pythonが見つかりません
echo Python 3.8以上をインストールしてください。
pause
exit /b 1

:install
echo Pythonコマンド: %PYTHON_CMD%
echo.
echo 依存パッケージをインストールします...
echo.

%PYTHON_CMD% -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [エラー] pipのアップグレードに失敗しました
    pause
    exit /b 1
)

%PYTHON_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [エラー] 依存パッケージのインストールに失敗しました
    pause
    exit /b 1
)

echo.
echo [完了] 依存パッケージのインストールが完了しました
echo.
pause



