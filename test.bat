@echo off
setlocal
if not exist .venv\Scripts\python.exe (
  echo Virtual environment not found.
  exit /b 1
)
.venv\Scripts\python.exe -m pytest -q
