# UPII v1.0 Release Strategy

**Release Manager**: Antigravity
**Version**: 1.0.0 "Sovereign Engine"
**Status**: GOLD CANDIDATE

---

## 1. v1.0 Readiness Checklist

### Core Features
- [x] **Ingestion**: Manual (CLI) + Passive (Watcher) + Temporal (Calendar).
- [x] **Retrieval**: Hybrid Search (Vector + Graph + Time).
- [x] **Interface**: Terminal + Global Overlay (`Cmd+Shift+K`).

### Trust & Safety
- [x] **Staging Isolation**: Ambient events do not write to LTM without approval.
- [x] **Auditability**: All passive events logged (`upii inbox`).
- [x] **Reversibility**: Graph data can be wiped (`upii knowledge wipe`).
- [x] **Telemetry**: Local-only metrics (`upii metrics export`).

### Quality Assurance
- [x] **Regression**: v0.5 tests pass.
- [x] **Integrity**: De-duplication verified.
- [x] **Stability**: Long-running (24h) simulation passed (<50MB memory growth).

---

## 2. Feature Flag Plan
We use a **Green/Blue Feature Toggle** strategy to allow incremental rollout even in a local binary.

**Config**: `features.yaml` (root of work directory).

| Feature Key | Default | Description |
| :--- | :--- | :--- |
| `ambient_memory` | **False** | Controls background file watching. Safer to start `False` on first install. |
| `global_overlay` | **True** | The new `Cmd+Shift+K` UI. Enabled by default as the flagship feature. |
| `knowledge_graph` | **True** | Entity extraction. Enabled. |
| `experimental_rag` | **False** | Any bleeding edge ranking algo (currently unused). |

**Strategy**: 
- If `ambient_memory` causes CPU spikes, user can set to `False` and restart to revert to v0.5 "Manual Only" mode.

---

## 3. Rollback Plan
In the event of catastrophic failure (Crash Loop, Data Corruption):

### Severity 1: Application Crash
**Action**: Disable Overlay and Ambient Memory.
1. `pkill -f upii`
2. Edit `features.yaml`:
   ```yaml
   ambient_memory: false
   global_overlay: false
   ```
3. Restart.

### Severity 2: Database Corruption
**Action**: Restore from Backup / Re-index.
1. `upii doctor` (Check integrity).
2. If `upii.db` invalid:
   - Rename `upii.db` to `upii.db.bak`.
   - Run `upii ingest . --force` to rebuild memory.

### Severity 3: Deployment Revert
**Action**: Re-install v0.5.
- Users can simply checkout the `v0.5` tag if distributed via git, or install the previous `.whl`.
- **Note**: `upii.db` schema v1 is backward compatible for READS but v0.5 cannot WRITE to new tables. Re-ingestion recommended if downgrading.

---

## 4. Known Limitations
Be transparent with users.

1.  **File Types**: Only supports text-based files (`.txt`, `.md`, `.py`, `.json`). PDFs and Images are **NOT** supported in v1.0.
2.  **Memory Usage**: The `chromadb` process and embeddings model (all-MiniLM-L6-v2) require ~500MB RAM steady state.
3.  **Calendar**: Limited to `.ics` file exports. No Real-time Google/Outlook API sync (Privacy decision).
4.  **Overlay**: macOS only. Linux/Windows support is experimental/beta.

---

## 5. What We Deliberately Did NOT Build (Anti-Roadmap)
Defining the product by what it is *not*.

1.  **Cloud Sync**: 
    - *Decision*: We will never build native cloud sync. This is **Sovereign** software. If you want sync, put your folder in Dropbox/iCloud, but we don't touch the network.
2.  **Mobile App**:
    - *Decision*: Focus is on "Deep Work" desktop productivity first. Mobile creates a server dependency we want to avoid for now.
3.  **Multi-User / Team Support**:
    - *Decision*: UPII is "Personal" Intelligence. Multi-user introduces ACLs, permission complexity, and trust vectors that dilute the single-user promise.
4.  **Proprietary LLMs (GPT-4 Integration)**:
    - *Decision*: Default is **Local**. We support OpenAI as a configurable backend, but the experience is designed to work fully offline. We will not "require" an API key.
