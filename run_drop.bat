@echo off
cd /d "%~dp0"
if "%~1"=="" (
  python tt.py
) else if /i "%~x1"==".url" (
  for /f "tokens=2 delims==" %%U in ('findstr /i "^URL=" "%~1"') do python tt.py "%%U"
) else (
  python tt.py "%~1"
)
