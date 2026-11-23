# Postmortem: 14 October 2025 Outage
Author: Nina Petrova. Date: 2025-10-16

## Impact
From 09:12 to 11:47 UTC, hubs could not upload readings and the Wrenfield dashboard showed stale data. No readings were lost: hubs buffered them and uploaded after recovery.

## Root cause
The TLS certificate on the device gateway expired. The automatic renewal job had been switched off during the CI runner migration in August and was never switched back on.

## Actions
1. Re-enable certificate auto-renewal (done).
2. Alert 30 days before any certificate expires (done).
3. Add certificate expiry to the weekly on-call checklist (done).
4. Add a gateway health check to the status page (done).
5. Review all jobs disabled during the CI migration (open).
6. Run a certificate-expiry game day (open).
