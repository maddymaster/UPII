# Architecture Overview
Owner: Daniel Okafor. Last updated: 2025-09-10

- Kestrin hubs connect to the device gateway over MQTT with TLS.
- The gateway writes readings to a time-series database.
- The Wrenfield application reads from the time-series database and a relational database for accounts and sites.
- The reporting service builds PDF and CSV reports from read replicas.
- Alerts go out through the SMS gateway and email.
