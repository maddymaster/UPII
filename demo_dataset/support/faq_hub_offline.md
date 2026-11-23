# FAQ: What happens when a hub goes offline?

Each Kestrin hub keeps logging readings during a network outage. It buffers up to 72 hours of readings and uploads them when the connection comes back, so the history in Wrenfield has no gap.
Alerts that trigger while the hub is offline are sent as soon as it reconnects.
If a hub stays offline for more than 30 minutes, Wrenfield marks it as offline and emails the account admin.
