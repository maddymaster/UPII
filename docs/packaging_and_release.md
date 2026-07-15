# UPII — Packaging & Installation Guide

This guide covers two ways to install UPII on **macOS** and **Windows 10/11**:

- **Method A — Install from source (recommended, all platforms).** A Python
  install via `pip`. Always works, smallest download, easiest to update.
- **Method B — Standalone binary (PyInstaller).** A single executable for users
  who don't want to manage Python. Larger (bundles PyTorch + the embedding stack)
  and currently **unsigned**, so the OS will warn on first launch.

> UPII is local-first: the corpus, embeddings and metadata never leave the
> machine. Both methods install the same CLI (`upii`).

---

## Prerequisites (both methods)

| Requirement | Notes |
|---|---|
| **Python 3.9+** | Only needed for Method A and for *building* a Method-B binary. End users of a prebuilt binary don't need Python. |
| **~1.5 GB disk** | The embedding model + dependencies (PyTorch). |
| **Embedding model** | `all-MiniLM-L6-v2` (~90 MB) auto-downloads on first ingest/search. One-time, then fully offline. |
| **Ollama** *(optional)* | Only for local LLM reasoning (`ask`, `write`). Install from <https://ollama.com> and `ollama pull llama3.2`. Without it, retrieval still works and reasoning falls back to a mock or optional Gemini. |

---

## Method A — Install from source (recommended)

Identical steps on macOS and Windows except for activating the virtual environment.

### macOS / Linux
```bash
git clone https://github.com/maddymaster/UPII.git
cd UPII
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .            # exposes the `upii` command
upii doctor                 # verify db, vectors, model, disk
```

### Windows (PowerShell)
```powershell
git clone https://github.com/maddymaster/UPII.git
cd UPII
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
upii doctor
```
> If activation is blocked, run once:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.

After install, `upii` is on PATH while the venv is active (or run
`python -m upii.cli` without installing).

---

## Method B — Build a standalone binary

The repo ships ready-to-use build scripts and a PyInstaller spec — **use these**
rather than hand-writing a `pyinstaller` command (they include the
`--collect-all` flags for `sentence_transformers`, `lancedb`, `ollama`, `typer`
and `pydantic` that the binary needs at runtime).

### Prerequisites
```bash
pip install -r requirements.txt    # requirements.txt already includes pyinstaller
```

### Build — macOS / Linux
```bash
./scripts/build.sh
# -> dist/upii        (runs `dist/upii --help` as a sanity check)
```

### Build — Windows (PowerShell or cmd)
```powershell
scripts\build.bat
:: -> dist\upii.exe   (runs dist\upii.exe --help as a sanity check)
```

### Alternative: build from the committed spec
Both platforms can also build directly from `upii.spec`:
```bash
pyinstaller upii.spec      # -> dist/upii  (dist\upii.exe on Windows)
```

**Output**

| Platform | Binary |
|---|---|
| macOS | `dist/upii` |
| Windows | `dist/upii.exe` |

> The binary is large (hundreds of MB) because it bundles PyTorch and the
> embedding runtime. The embedding model itself still downloads on first run.

---

## Running UPII (end users)

### macOS
```bash
chmod +x upii            # if delivered as a bare binary
./upii doctor
./upii ingest ~/Documents/MyNotes --recursive
./upii ask "What is my plan?"
```
> **Gatekeeper:** an unsigned binary is blocked on first launch. Right-click the
> file → **Open** → **Open**, or run
> `xattr -d com.apple.quarantine ./upii` once. (Code signing is a future
> release step.)

### Windows
```powershell
.\upii.exe doctor
.\upii.exe ingest C:\Users\Me\Documents --recursive
.\upii.exe ask "What is my plan?"
```
> **SmartScreen:** an unsigned `.exe` shows "Windows protected your PC." Click
> **More info → Run anyway**.

(For a Method-A install, drop the `./` / `.exe` and just use `upii ...`.)

---

## Quick demo

A sample corpus lives in `demo_dataset/`.

**macOS / Linux**
```bash
rm -f upii.db upii.log && rm -rf upii_vectors      # clean slate
upii doctor
upii ingest ./demo_dataset --recursive
upii ask "What is the budget?"
```

**Windows (PowerShell)**
```powershell
Remove-Item upii.db, upii.log -ErrorAction SilentlyContinue
Remove-Item upii_vectors -Recurse -ErrorAction SilentlyContinue
upii doctor
upii ingest .\demo_dataset --recursive
upii ask "What is the budget?"
```

For a deterministic re-ingestion demo, see `scripts/demo/repro_demo.sh`.

---

## Versioning

UPII follows **Semantic Versioning** (`MAJOR.MINOR.PATCH`). The canonical
version is in `pyproject.toml` (currently **0.5.0**).

Tag a release to trigger the build pipeline:
```bash
git tag v0.5.0
git push origin v0.5.0
```

---

## Release pipeline (GitHub Actions)

`.github/workflows/release.yml` runs on any `v*` tag:

1. **Build job** — matrix over `macos-latest` and `windows-latest`: checkout →
   set up Python 3.9 → `pip install -r requirements.txt` → run
   `scripts/build.sh` (mac) / `scripts\build.bat` (windows). Each build runs a
   `--help` sanity check.
2. **Upload** — each OS uploads its binary as artifact `upii-<os>`
   (`upii-macOS`, `upii-Windows`).
3. **Release job** — downloads both artifacts and publishes a GitHub Release
   with `dist/upii` and `dist/upii.exe` attached.

> **Maintenance note:** the workflow uses `actions/upload-artifact@v4` /
> `download-artifact@v4` (the v3 versions GitHub disabled in early 2025). Keep
> these on a supported major version or the release job will fail.

### Not yet automated
- **Code signing / notarization** (macOS) and **Authenticode signing**
  (Windows) — binaries are currently unsigned; users must bypass Gatekeeper /
  SmartScreen as noted above.
