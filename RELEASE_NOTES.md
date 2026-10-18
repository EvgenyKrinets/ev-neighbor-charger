# EV Neighbor Charger 0.4.16

- Scheduled charging with immediate reservation, owner and planned start display.
- Owner/admin can edit, cancel or start now. Reservations survive HA restarts and reloads.
- Launch occurs in HA; the app can be closed. Errors are displayed and retried.
- Accounting begins at activation, excluding reservation waiting time.
- No no-load waiting timeout for scheduled sessions; the existing end timer applies after first load.
- Russian, English and Hebrew UI and documentation updated.
