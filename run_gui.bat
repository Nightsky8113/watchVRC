@echo off
chcp 65001 > nul
echo ========================================
echo V睡録画ソフト - GUI起動
echo ========================================
echo.

REM Pythonコマンドを確認（pyコマンドを優先）
where py >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Pythonが見つかりました (pyコマンド)
    set PYTHON_CMD=py
    goto :run
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Pythonが見つかりました
    set PYTHON_CMD=python
    goto :run
)

echo [エラー] Pythonが見つかりません
echo.
echo Pythonがインストールされているか確認してください。
echo Python 3.8以上が必要です。
echo.
pause
exit /b 1

:run
echo.
echo GUIアプリケーションを起動しています...
echo.

REM 依存パッケージの確認（簡易チェック）
%PYTHON_CMD% -c "import customtkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 依存パッケージがインストールされていません
    echo.
    echo 依存パッケージをインストールしますか？ (Y/N)
    set /p install=
    if /i "%install%"=="Y" (
        echo.
        echo 依存パッケージをインストール中...
        %PYTHON_CMD% -m pip install -r requirements.txt
        if %errorlevel% neq 0 (
            echo.
            echo [エラー] インストールに失敗しました
            echo install.bat を実行して手動でインストールしてください
            echo.
            pause
            exit /b 1
        )
        echo.
        echo [OK] インストール完了
        echo.
    ) else (
        echo インストールをスキップします
        echo install.bat を実行して手動でインストールしてください
        echo.
        pause
        exit /b 1
    )
)

REM GUIアプリケーションを起動
%PYTHON_CMD% gui_app.py
if %errorlevel% neq 0 (
    echo.
    echo [エラー] アプリケーションの起動に失敗しました
    echo エラーメッセージを確認してください。
    echo.
    pause
    exit /b %errorlevel%
)

pause

:end
echo.
echo GUIアプリケーションを終了します。
echo.
pause
exit /b 0