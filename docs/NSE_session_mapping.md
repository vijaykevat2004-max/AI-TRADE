# Sessions

SOURCE article says 09:30–11:30 EST, corresponding 20:00–22:00 IST at UTC-5; EDT instead gives 19:00–21:00. Its daylight-saving intent is unresolved. Neither describes NSE cash. Asian/London forex ranges are not relabelled NSE ranges.

PROPOSED_NSE_WINDOW_A: cash regular 09:15–15:30 Asia/Kolkata, opening range 09:15–09:30, experimental entry 09:30–11:30, expiry 15:20. UTC conversion uses aware datetimes. A year-matched official CM holiday calendar is required during market hours. Dated special-session overrides are supported; exchange-notice audit is still a production blocker. Weekend/closed never triggers source fetch or fresh evaluation. Source calendar failure during regular hours is CALENDAR_UNKNOWN, never silently a holiday.
