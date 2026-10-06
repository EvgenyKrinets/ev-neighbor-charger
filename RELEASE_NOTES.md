## EV Neighbor Charger 0.4.0

- New charging panel with a prominent charging user, larger live metrics, teal accents, mobile layout and Hebrew RTL support.
- Start button disappears while starting or while the charger is occupied.
- Options now separate charging/access from outgoing email.
- Google/Gmail, Yahoo and Apple iCloud presets automatically fill SMTP host, port, encryption and sender. Enter your email and app password only.
- Existing custom SMTP settings are preserved. Blank password keeps an existing password only for the same provider and username.
- Microsoft is clearly marked as requiring OAuth; password-only Microsoft setup is not supported and cannot be saved as a working connection.

Update through HACS, restart Home Assistant and reopen the charging panel. For email: integration options → Outgoing email → choose provider. Use an app password issued by your provider, not a regular account password.
