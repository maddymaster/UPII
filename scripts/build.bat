@echo off
echo Building UPII v1.0 for Windows...

:: Install PyInstaller, and pin setuptools<81: setuptools 81 removed
:: pkg_resources.NullProvider, which PyInstaller's runtime hook needs. PyInstaller
:: bundles the build-env's pkg_resources, so a newer setuptools crashes the frozen
:: binary at launch. (setuptools' own warning recommends "pin to Setuptools<81".)
pip install "setuptools<81" pyinstaller

:: Clean previous builds (keep the committed upii.spec)
if exist build rd /s /q build
if exist dist rd /s /q dist

:: Build (PyInstaller appends .exe on Windows -> dist\upii.exe)
pyinstaller --name upii ^
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
