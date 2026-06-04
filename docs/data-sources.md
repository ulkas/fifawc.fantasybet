# Data Sources

The app stores source snapshots before parsing so the schedule/results can be audited and reprocessed offline.

Primary source:

- FIFA World Cup 2026 public schedule/results pages.

Structured free seed/cross-check:

- OpenFootball World Cup JSON: `https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json`

The first v1 parser imports OpenFootball JSON as the structured schedule and stores raw FIFA pages for canonical audit. Score sync updates only final scores available in the structured source and records conflicts if a stored final score differs from incoming data.
