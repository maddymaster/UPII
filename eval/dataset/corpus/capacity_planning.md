# Capacity Planning

Estimated index size grows ~1MB per 1,000 chunks. For a heavy user with 200k
chunks we project ~200MB resident, comfortably under the 500MB cap. Re-embedding
the whole corpus takes about 6 minutes on a laptop.
