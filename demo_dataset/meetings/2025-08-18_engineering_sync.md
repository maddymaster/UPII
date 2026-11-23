# Engineering Sync
Date: 2025-08-18
Attendees: Daniel Okafor, Hiro Tanaka, Nina Petrova, Ravi Kulkarni, Mei Chen

## Updates
- Hiro: the Wrenfield dashboard now loads the device list in under two seconds for accounts with 5,000 devices.
- Nina: the new CI runners cut the average pipeline time from 22 to 9 minutes.
- Ravi: the CSV export still drops rows with non-ASCII site names. Fix planned for Wrenfield 3.2.
- Mei: started the Bluetooth pairing rewrite for firmware 2.0 (Project Ember).

## Decisions
- Code freeze for each Wrenfield release is the Wednesday before release day.
- All new services must emit structured logs from day one.

## Action items
- Ravi to write a regression test for the CSV export bug.
- Nina to decommission the old CI runners by the end of the month.
