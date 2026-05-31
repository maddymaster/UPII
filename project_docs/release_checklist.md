# UPII v0.5 Release Checklist

## 1. Environment Verification
- [ ] `python --version` is >= 3.9
- [ ] `pip freeze | grep torch`
- [ ] `ollama serve` is running in background

## 2. Clean Install Test
- [ ] Delete `venv` and recreate
- [ ] `pip install -r requirements.txt`
- [ ] `python -m upii.cli doctor` returns clean health

## 3. Functional Verification
- [ ] **Ingest**: `python -m upii.cli ingest demo_dataset/` -> Success
- [ ] **Search**: `python -m upii.cli search "Omega"` -> Returns chunks
- [ ] **Ask**: `python -m upii.cli ask "Who fixed the leak?"` -> "Sarah"
- [ ] **Tasks**: `python -m upii.cli tasks list` -> Shows extracted tasks
- [ ] **Persistence**: Restart terminal, query again -> Data persists

## 4. Performance Check
- [ ] `upii.cli ingest` took < 5 seconds for demo dataset
- [ ] `upii.cli ask` response time < 5 seconds

## 5. Artifacts
- [ ] `demo_script.md` available
- [ ] `qa_plan.md` available
- [ ] `walkthrough.md` updated
