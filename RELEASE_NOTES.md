# EV Charger 0.4.18

- Add an administrator-only **⚙ integration settings** shortcut to the panel. Home Assistant configuration remains managed by its native **Configure** flow, while **@** still opens the individual email profile.
- Recognize an externally switched-on charging station, show **In use by another application** in RU/EN/HE, and prevent overlapping starts without shutting down or billing the external charging session.
- Keep reservation, scheduled charging, delayed power-detection behavior and existing low-power shutoff rules; never add the unwanted 30-minute pre-load timer.
- Align display names with **EV Charger** without changing the stored domain, installation identity, history or users.
- Refresh documentation and setup guidance, including the difference between Helpers and Integrations and safe migration from 0.4.16.
- Regression tests for the administrator settings shortcut, external charger state and existing scheduling.
