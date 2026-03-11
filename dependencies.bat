@echo off
setlocal
echo ============================================
echo  Ez-TikTok-Downloader - Full setup
echo ============================================
echo.

:: Check for Python (python3 or python)
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
  goto :have_python
)
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
  set PY_LAUNCHER=1
  goto :have_python
)
goto :no_python

:have_python
echo [1/3] Python found.
if defined PY_LAUNCHER (
  py -3 --version
  set "PYCMD=py -3"
) else (
  python --version
  set "PYCMD=python"
)
echo.
goto :install_deps

:no_python
echo [1/3] Python not found. Trying to install via winget...
where winget >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo.
  echo winget is not available. Please install Python manually:
  echo   1. Open https://www.python.org/downloads/
  echo   2. Download Python 3.12 or newer
  echo   3. Run the installer and CHECK "Add Python to PATH"
  echo   4. Close this window, open a new one, then run this bat again.
  echo.
  pause
  exit /b 1
)
winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Python was installed. Please CLOSE this window, open a new Command Prompt,
echo go to this folder again, and run dependencies.bat again.
echo.
pause
exit /b 0

:install_deps
echo [2/3] Upgrading pip...
"%PYCMD%" -m pip install --upgrade pip
echo.
echo [3/3] Installing Python packages from requirements.txt...
"%PYCMD%" -m pip install -r requirements.txt
echo.
echo ============================================
echo  Setup complete. Use run.bat or: python tt.py
echo ============================================
pause
