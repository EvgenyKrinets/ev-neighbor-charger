# 0.4.12

- Fix broken logo and presentation images in HACS by using absolute raw GitHub image URLs in README.

# 0.4.11

- Email profile button now uses @.
- Administrators have a Home Assistant menu button at the top left.
- Live charging phases: preparing before the first load above the configured idle threshold, charging above it, finishing after power falls to/below it. Load history is persisted across restarts; renewed load returns to charging.
- History filters for today, last 7 calendar days, this month and all time; admins can search by user name. Periods use the viewing device timezone and session start time.
- History no longer truncates at 100 sessions; non-admins only receive their own sessions.
- RU/EN/HE labels and regression checks for phases, authorization, periods and names.
