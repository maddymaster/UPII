#!/bin/bash
set -e

echo "Building UPII v1.0 for macOS..."

# Install PyInstaller if not present
pip install pyinstaller

# Clean previous builds
rm -rf build dist *.spec

# Build
pyinstaller --name upii \
    --onefile \
    --clean \
    --collect-all "sentence_transformers" \
    --collect-all "lancedb" \
    --collect-all "ollama" \
    --collect-all "typer" \
    --collect-all "pydantic" \
    --hidden-import="lancedb" \
    --hidden-import="pandas" \
    --hidden-import="pkg_resources.extern" \
    --exclude-module="PyQt5" \
    --exclude-module="PySide6" \
    --exclude-module="PyQt6" \
    --exclude-module="tkinter" \
    --paths "src" \
    src/upii/cli.py

echo "Build complete. Binary at dist/upii"

# Sanity Check
echo "Running Sanity Check..."
./dist/upii --help
