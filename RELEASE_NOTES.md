# v0.4.7

- Automatically open the charging panel for selected restricted non-admin users.
- Hide Home Assistant navigation and header in restricted charging mode; guard navigation including Back and direct frontend links.
- Remove general entity permissions from managed users instead of granting read-only access to all entities. Restore original groups when restriction is disabled, users are removed, or the integration is removed.
- Authorize charging snapshots and live subscriptions on the server, including each pushed update.
- Existing email profile, SMTP test, Brevo and Mailjet configuration are retained.

Kiosk navigation is a frontend restriction, not a security boundary for every Home Assistant API. General entity access is denied through Home Assistant permissions, but complete isolation from all HA metadata requires a separate portal/account system. Restart HA and fully reopen clients after updating; verify with a non-admin account on the installed HA version.

## EV Neighbor Charger 0.4.6

- Hide the user's email form after saving; reopen it with the settings button in the charging panel.
- Move SMTP testing from the user's charging panel to integration options.
- Test current or newly entered SMTP settings with a selected saved address or a manually entered recipient.
- Show SMTP acceptance or delivery errors directly in the options form. Sending acceptance does not guarantee inbox delivery.
- Preserve existing sensor-editing options and live charging updates.
