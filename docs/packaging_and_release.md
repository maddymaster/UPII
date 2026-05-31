# UPII v0.5 Packaging & Release Guide

## 1. Overview
UPII v0.5 is packaged as a standalone executable using `PyInstaller`. This removes the requirement for end-users to manage Python environments or dependencies manually.

**Target Platforms:**
- macOS (Universal 2 / ARM64)
- Windows 10/11 (x64)

## 2. Packaging Instructions (Dev)

### Prerequisites
- Python 3.9+ installed
- `pip install -r requirements.txt`
- `pip install pyinstaller`

### Build Command (Mac/Linux)
```bash
pyinstaller --name upii \
    --onefile \
    --add-data "src/upii:upii" \
    --hidden-import="sklearn.utils._cython_blas" \
    --hidden-import="sklearn.neighbors.typedefs" \
    --hidden-import="sklearn.neighbors.quad_tree" \
    --hidden-import="sklearn.tree._utils" \
    --hidden-import="lancedb" \
    --hidden-import="pandas" \
    --collect-all "sentence_transformers" \
    src/upii/cli.py
```
*Note: `scikit-learn` and `sentence-transformers` often require explicit hidden imports or data collection.*

### Build Command (Windows)
```powershell
pyinstaller --name upii.exe ^
    --onefile ^
    --add-data "src/upii;upii" ^
    --collect-all "sentence_transformers" ^
    src/upii/cli.py
```

### Output
The binary will be located in the `dist/` directory:
- Mac: `dist/upii`
- Windows: `dist/upii.exe`

## 3. How to Run (End-User)

### macOS
1. Open Terminal.
2. Navigate to the download location.
3. Make executable: `chmod +x upii`
4. Run:
   ```bash
   ./upii doctor
   ./upii ingest ~/Documents/MyNotes
   ./upii ask "What is my plan?"
   ```
   *Note: On first run, MacOS Gatekeeper might block it. Right-click > Open to bypass.*

### Windows
1. Open PowerShell or Command Prompt.
2. Navigate to the folder.
3. Run:
   ```powershell
   .\upii.exe doctor
   .\upii.exe ingest C:\Users\Me\Documents
   ```

## 4. Demo Instructions (Binary Version)
The flow is identical to the Python script version, but invoked via the binary.

1. **Clean Start**:
   ```bash
   rm upii.db upii.log
   rm -rf upii_vectors
   ```
2. **Check Health**:
   ```bash
   ./upii doctor
   ```
3. **Ingest**:
   ```bash
   ./upii ingest ./demo_dataset
   ```
4. **Interact**:
   ```bash
   ./upii ask "What is the budget?"
   ```

## 5. Versioning Strategy
We adhere to **Semantic Versioning (SemVer)**: `MAJOR.MINOR.PATCH`
- **v0.5.0**: Initial Local-First Beta (Current).
- **v0.5.x**: Bug fixes, performance patches.
- **v0.6.0**: New features (e.g., Image support, Web UI).

**Tagging**:
Git tags trigger the release pipeline.
```bash
git tag v0.5.0
git push origin v0.5.0
```

## 6. Release Pipeline (GitHub Actions)
The configured workflow (`.github/workflows/release.yml`) automatically:
1. Triggers on tags starting with `v*`.
2. checkouts code.
3. Sets up Python.
4. Installs dependencies + PyInstaller.
5. Builds the binary (runs on `macos-latest` and `windows-latest` in parallel).
6. Runs sanity tests on the binary.
7. Creates a GitHub Release and uploads the artifacts (`upii-macos`, `upii-windows.exe`).
