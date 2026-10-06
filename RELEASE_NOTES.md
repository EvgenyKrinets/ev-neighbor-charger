## EV Neighbor Charger 0.3.3

- Push live power, energy and session data directly from the integration over WebSocket when sensors change.
- Prevent stale frontend entity data and delayed polling replies from overwriting newer readings.
- Recover after mobile app resume, network changes and integration reloads; time out stalled requests so polling cannot remain blocked indefinitely.
- Keep the charging user's name and existing email form values.
- Unavailable energy readings now display a dash instead of a misleading zero.

Install through HACS, restart Home Assistant and reopen the panel. Values update when the configured sensors report; this cannot increase the device's own reporting rate.
