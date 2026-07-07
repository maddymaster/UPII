# Weekly Team Sync Notes

Sarah tracked down and fixed the memory leak in the file watcher — it was an
unbounded event queue that grew during large ingests. Fix shipped Tuesday.
Raj is the onboarding buddy for our new hire starting next week; he'll walk them
through the ingestion pipeline and the local-first data model.
