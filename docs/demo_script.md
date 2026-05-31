# UPII v0.5 Stakeholder Demo Script (5 Minutes)

**Goal**: Demonstrate reliable, private local memory with instant recall and task tracking.

## 0. Setup (Pre-Demo)
1. **Clean Slate**:
   ```bash
   rm upii.db upii.log
   rm -rf upii_vectors
   ```
2. **Activate Environment**:
   ```bash
   source venv/bin/activate
   ```

## 1. Introduction (30s)
*Say*: "Today we are demoing UPII v0.5, our local-first personal memory engine. It runs entirely on-device with zero data egress."

**Action**: Show System Health.
```bash
python -m upii.cli doctor
```
*Expect*: "OK" on all checks.

## 2. Ingestion & Auto-Tagging (1m)
*Say*: "Let's ingest our project notes. Watch for automatic task extraction."

**Action**: Ingest Golden Dataset.
```bash
python -m upii.cli ingest demo_dataset/
```
*Expect*: Output showing 3 files processed and tasks extracted in magenta.

## 3. Retrieval & Reasoning (2m)
*Say*: "Now I'll ask a complex question that requires synthesizing information across files."

**Action**: Ask about Project Omega.
```bash
python -m upii.cli ask "What are the key decisions for Project Omega?"
```
*Expect*: Answer citing `all-MiniLM-L6-v2` and `no cloud syncing`.

**Action**: Ask about Financials.
```bash
python -m upii.cli search "budget 2026"
```
*Expect*: Retrieval of chunks from `financials.txt`.

## 4. Task Management (1m)
*Say*: "The system automatically captured action items from our meeting notes."

**Action**: List tasks.
```bash
python -m upii.cli tasks list
```
*Expect*: "Research optimal chunk header size", "Update README", "Fix doctor command".

**Action**: Complete a task.
```bash
python -m upii.cli tasks done README
python -m upii.cli tasks list
```
*Expect*: The README task disappears from the pending list.

## 5. Privacy & Trust (30s)
*Say*: "Finally, if it doesn't know, it says so. No hallucinations."

**Action**: Ask unknown question.
```bash
python -m upii.cli ask "What is the launch date for Project Alpha?"
```
*Expect*: "I don't know" or "No relevant context found".

*Closing*: "This is UPII v0.5: Private, Reliable, Available."
