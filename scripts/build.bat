@echo off
echo Building UPII v1.0 for Windows...

:: Install PyInstaller if not present
pip install pyinstaller

:: Clean previous builds
if exist build rd /s /q build
if exist dist rd /s /q dist
if exist *.spec del *.spec

:: Build
pyinstaller --name upii.exe ^
    --onefile ^
    --clean ^
    --collect-all "sentence_transformers" ^
    --collect-all "lancedb" ^
    --collect-all "ollama" ^
    --collect-all "typer" ^
    --collect-all "pydantic" ^
    --hidden-import="lancedb" ^
    --hidden-import="pandas" ^
    --hidden-import="pkg_resources.extern" ^
    --exclude-module="PyQt5" ^
    --exclude-module="PySide6" ^
    --exclude-module="PyQt6" ^
    --exclude-module="tkinter" ^
    --paths "src" ^
    src/upii/cli.py

echo Build complete. Binary at dist\upii.exe

:: Sanity Check
echo Running Sanity Check...
dist\upii.exe --help
