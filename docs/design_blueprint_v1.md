# UPII v1.0: Sovereign Memory Engine - Technical Blueprint

**Goal**: Upgrade from Explicit Memory (v0.5) to Ambient Memory (v1.0) with zero trust compromise.

## 1. Upgrade Philosophy
1.  **Isolation**: Passive features must never corrupt the core `upii.db`. They write to a separate `staging.db`.
2.  **Opt-In**: All ambient features require explicit activation via Feature Flags.
3.  **Human-in-the-Loop**: Passive ingestion does not go to Long Term Memory (LTM) immediately. It goes to an "Inbox" (Staging) for review or auto-policy approval.

## 2. System Architecture (v1.0)

```mermaid
graph TD
    subgraph "Core (v0.5 Reliability)"
        CLI[CLI Commands]
        LTM[(v0.5 Memory DB)]
        Vec[(Vector Store)]
        Ingest[Explicit Ingest]
        
        CLI --> Ingest
        Ingest --> LTM
        Ingest --> Vec
    end

    subgraph "Ambient Extensions (v1.0)"
        Watcher[File Watcher]
        Staging[(Staging DB)]
        Flags[Feature Flags]
        Review[Inbox Review]
        
        Watcher -.->|Change Event| Staging
        Review -->|Approve| Ingest
        Review -->|Reject| Staging
        
        Watcher -- Read --> Flags
    end
    
    %% Isolation
    Watcher --X LTM
    Watcher --X Vec
```

## 3. Component Separation

| Feature | v0.5 (Explicit) | v1.0 (Passive/Ambient) |
| :--- | :--- | :--- |
| **Trigger** | User runs `upii ingest` | FileSystem Event (Create/Mod) |
| **Scope** | Targeted Directory | Watched Folders (recursive) |
| **Destination** | Production DB (`upii.db`) | Staging DB (`staging.db`) |
| **Trust Level** | Verified (User Initiated) | Low (Auto-Captured) |
| **Process** | Foreground (Blocking) | Background (Daemon/Thread) |

## 4. Failure Isolation Strategy
1.  **Process Isolation**: The `Watcher` runs in a separate daemon thread (or process). Uncaught exceptions in the watcher loop are caught, logged to `ambient.log`, and do not crash the main CLI.
2.  **Data Isolation**: Passive ingestion writes ONLY to `staging.db` (SQLite). It creates no embeddings and alters no vectors until "Promoted".
3.  **Crash Safety**: `staging.db` uses WAL mode. Corrupt passive data can be wiped (`upii inbox --purge`) without affecting LTM.

## 5. Feature Flags (`flags.yaml`)
New features are guarded by strict flags. Default state is `False`.

```yaml
features:
  ambient_memory:
    enabled: false
    watch_paths: []
    file_types: [".md", ".txt"]
    auto_commit: false # Breaking trust constraint if true
```

## 6. Implementation Stages
1.  **Infrastructure**: Feature Flags & Staging DB schema.
2.  **Watcher**: Logic to monitor `watch_paths` and write events to Staging.
3.  **Interface**: `upii inbox` to list, diff, and promote items from Staging to LTM.
