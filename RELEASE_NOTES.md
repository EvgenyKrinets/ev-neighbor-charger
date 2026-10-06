## EV Neighbor Charger 0.3.1

- Numbered GitHub release for HACS instead of a branch commit identifier.
- Running integration version and local brand icon in the charging panel.
- Suggest the signed-in user's own local login when it is an email address; explicit Save is required before sending reports.
- Fix unnamed-user fallback (Home Assistant User has no username property).
- Includes 0.3.0 live readings, Russian/English/Hebrew UI and start/end/monthly email reports.

Update through HACS, select v0.3.1, restart Home Assistant and refresh the panel.

Known limitation: HACS update entities that request icons directly from brands.home-assistant.io still show a placeholder for this integration. Its bundled local brand images work in supported Home Assistant integration views and in the charging panel.
