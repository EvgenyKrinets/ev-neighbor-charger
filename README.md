# EV Neighbor Charger

Custom Home Assistant integration for shared EV charging with per-user session accounting and automatic shutoff.

## First version

- UI setup: select the relay, cumulative energy sensor, power sensor and allowed Home Assistant users.
- Optional read-only restriction: selected neighbors are moved into Home Assistant's built-in **Read Only** group. Their previous group membership is saved and restored when they are removed from the allow-list or this integration is removed.
- Integrated sidebar page with a **Start charging** button.
- The active user's identity comes from the authenticated Home Assistant WebSocket connection; the browser cannot choose another user's name.
- Automatically turns the relay off when power stays below the configured threshold for the configured delay (defaults: 100 W for 2 minutes).
- Stores sessions locally in Home Assistant and shows energy and cost totals.
- Stops a session if the relay is switched off outside the integration.

Read-only mode prevents selected users from controlling entities directly in Home Assistant. It also makes their other dashboards read-only, and their accounts can still see entity states in Home Assistant. Home Assistant does not provide a strict per-user sandbox that permits only one dashboard. Hide other sidebar items and set the charging page as their default for a focused interface.

The integration stores selected users' previous Home Assistant group memberships and restores them if they are removed from the allow-list or the integration is removed. The read-only option is enabled by default in the setup form; uncheck it if you do not want the integration to change user groups.

## Install

This repository is structured for HACS as a custom integration. Add the GitHub repository in HACS → Integrations → ⋮ → Custom repositories (category **Integration**), download it, restart Home Assistant, then add **EV Neighbor Charger** from Settings → Devices & services.

No YAML changes are required. HACS custom-repository installation is available once the repository has been published on GitHub.

## Notes

This is an initial release. Test the selected relay and sensors while present before relying on automatic shutoff. The integration will only auto-switch-off an active session it started. A switch already on before a session starts is treated as busy.
