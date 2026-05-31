# UPII v1.0: User Installation Guide

Welcome to the **Unified Personal Intelligence Interface (UPII)** private preview.
This guide will help you set up the standalone executable on your machine.

> [!WARNING]
> **Beta Software**: This is un-signed software. You may need to bypass OS security warnings (Mac "Unidentified Developer" / Windows SmartScreen).

---

##  macOS Installation (Apple Silicon & Intel)

**Prerequisites**: macOS 12 Monterey or later.

1.  **Download & Extract**
    *   Download `upii_v1.0_mac.zip` from the secure share.
    *   Double-click to unzip. You should see a binary file named `upii`.

2.  **Install to Path**
    Open your Terminal and run:
    ```bash
    # Move to a directory in your PATH
    sudo mv ~/Downloads/upii /usr/local/bin/upii
    
    # Make executable
    sudo chmod +x /usr/local/bin/upii
    ```

3.  **Security Bypass (First Run Only)**
    *   Run `upii doctor` in the terminal.
    *   **Pop-up**: "MacOS cannot verify the developer of 'upii'." -> Click **Cancel**.
    *   Go to **System Settings > Privacy & Security**.
    *   Scroll down to Security. You will see "upii was blocked...". Click **Allow Anyway**.
    *   Run `upii doctor` again. Click **Open**.

4.  **Verification**
    ```bash
    upii --help
    # Success if you see the help menu.
    ```

---

## ⊞ Windows Installation (Win 10/11)

**Prerequisites**: Windows 10 build 19041 or later.

1.  **Download & Extract**
    *   Download `upii_v1.0_win.zip`.
    *   Right-click > **Extract All**. Folder: `C:\Tools\UPII` (Recommended).

2.  **Add to Path (Optional but Recommended)**
    *   Search "Edit the system environment variables" in Start Menu.
    *   Click **Environment Variables** > **Path** > **Edit** > **New**.
    *   Paste: `C:\Tools\UPII`.

3.  **First Run (PowerShell)**
    *   Open PowerShell.
    *   Navigate to the folder: `cd C:\Tools\UPII`
    *   Run: `.\upii.exe doctor`

4.  **SmartScreen Warning**
    *   **Blue Screen**: "Windows protected your PC".
    *   Click **More Info** > **Run Anyway**.

---

## 🚀 Getting Started

### 1. Initialize the Brain
UPII needs to create its local database.
```bash
upii demo seed
# Output: Seeded Project Omega / Ambee data.
```

### 2. The Verification Test
Ask a question to prove the system is running locally.

**Mac/Linux:**
```bash
upii ask "What is the ICEYE latency?"
```

**Windows:**
```powershell
.\upii.exe ask "What is the ICEYE latency?"
```

### 3. Ingesting Your Own Data
To index a folder of markdown notes:
```bash
upii memory add "/Users/maddy/ObsidianVault"
```

---

## 🆘 Troubleshooting

**Q: "I don't know (no relevant context found)"?**
A: Run `upii demo seed` again to reset the database.

**Q: It's slow?**
A: First run is slow (model loading). Subsequent queries should take <300ms.

**Q: Antivirus blocked it?**
A: Whitelist `upii` (Mac) or `upii.exe` (Windows). We rely on `lancedb` which some scanners flag as generic "Packer" behavior due to PyInstaller.
