@echo off
setlocal
if not exist .venv\Scripts\python.exe (
  echo Virtual environment not found.
  echo Create it with: py -3.12 -m venv .venv
  exit /b 1
)
.venv\Scripts\python.exe main.py
