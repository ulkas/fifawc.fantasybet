from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from fantasy.models import DataSnapshot, Match, Team, Venue


def flag_emoji(country_code: str) -> str:
    return "".join(chr(0x1F1E6 + ord(letter) - ord("A")) for letter in country_code)


COUNTRY_FLAGS = {
    "Argentina": ("ARG", flag_emoji("AR")),
    "Australia": ("AUS", flag_emoji("AU")),
    "Belgium": ("BEL", flag_emoji("BE")),
    "Brazil": ("BRA", flag_emoji("BR")),
    "Canada": ("CAN", flag_emoji("CA")),
    "Cote d'Ivoire": ("CIV", flag_emoji("CI")),
    "Czech Republic": ("CZE", flag_emoji("CZ")),
    "Ecuador": ("ECU", flag_emoji("EC")),
    "Egypt": ("EGY", flag_emoji("EG")),
    "England": ("ENG", "\U0001f3f4"),
    "France": ("FRA", flag_emoji("FR")),
    "Germany": ("GER", flag_emoji("DE")),
    "Ghana": ("GHA", flag_emoji("GH")),
    "IR Iran": ("IRN", flag_emoji("IR")),
    "Japan": ("JPN", flag_emoji("JP")),
    "Mexico": ("MEX", flag_emoji("MX")),
    "Morocco": ("MAR", flag_emoji("MA")),
    "Netherlands": ("NED", flag_emoji("NL")),
    "New Zealand": ("NZL", flag_emoji("NZ")),
    "Portugal": ("POR", flag_emoji("PT")),
    "Qatar": ("QAT", flag_emoji("QA")),
    "Saudi Arabia": ("KSA", flag_emoji("SA")),
    "Scotland": ("SCO", "\U0001f3f4"),
    "South Africa": ("RSA", flag_emoji("ZA")),
    "Spain": ("ESP", flag_emoji("ES")),
    "Switzerland": ("SUI", flag_emoji("CH")),
    "Tunisia": ("TUN", flag_emoji("TN")),
    "Uruguay": ("URU", flag_emoji("UY")),
    "USA": ("USA", flag_emoji("US")),
}


@dataclass
class FetchResult:
    payload: str
    content_type: str


def fetch_url(url: str) -> FetchResult:
    request = Request(url, headers={"User-Agent": "wcf-fantasy/1.0"})
    with urlopen(request, timeout=30) as response:
        raw = response.read()
        return FetchResult(raw.decode("utf-8", errors="replace"), response.headers.get("Content-Type", ""))


def store_snapshot(source: str, url: str, payload: str, content_type: str = "", parsed_ok: bool = False, parse_message: str = "") -> DataSnapshot:
    return DataSnapshot.objects.create(
        source=source,
        url=url,
        payload=payload,
        content_type=content_type,
        parsed_ok=parsed_ok,
        parse_message=parse_message,
    )


def load_payload(source: str, url: str | None = None, file_path: str | None = None) -> DataSnapshot:
    if file_path:
        with open(file_path, "r", encoding="utf-8") as handle:
            payload = handle.read()
        return store_snapshot(source, file_path, payload, "local/file")
    if not url:
        raise ValueError("A URL or file path is required.")
    fetched = fetch_url(url)
    return store_snapshot(source, url, fetched.payload, fetched.content_type)


def parse_openfootball_datetime(date_value: str, time_value: str) -> datetime:
    clean_time = (time_value or "00:00").strip()
    match = re.match(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?:\s*UTC(?P<offset>[+-]\d+))?", clean_time)
    if not match:
        naive = datetime.fromisoformat(f"{date_value}T00:00:00")
        return timezone.make_aware(naive, dt_timezone.utc)
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    offset = int(match.group("offset") or "0")
    local_tz = dt_timezone.utc if offset == 0 else dt_timezone.utc
    aware_as_utc = datetime.fromisoformat(f"{date_value}T{hour:02d}:{minute:02d}:00").replace(tzinfo=dt_timezone.utc)
    if offset:
        aware_as_utc = aware_as_utc.replace(hour=hour) - timedelta(hours=offset)
    return aware_as_utc.astimezone(dt_timezone.utc)


def stage_from_record(record: dict) -> str:
    group = record.get("group") or ""
    round_label = (record.get("round") or "").lower()
    if group:
        return Match.Stage.GROUP
    if "round of 32" in round_label:
        return Match.Stage.ROUND_OF_32
    if "round of 16" in round_label:
        return Match.Stage.ROUND_OF_16
    if "quarter" in round_label:
        return Match.Stage.QUARTER_FINAL
    if "semi" in round_label:
        return Match.Stage.SEMI_FINAL
    if "third" in round_label:
        return Match.Stage.THIRD_PLACE
    if "final" in round_label:
        return Match.Stage.FINAL
    return Match.Stage.GROUP


def get_or_create_team(label: str) -> Team | None:
    if not label or "/" in label or label.lower().startswith(("winner ", "group ", "runner", "third ")):
        return None
    iso_code, flag = COUNTRY_FLAGS.get(label, ("", ""))
    team, _ = Team.objects.update_or_create(name=label, defaults={"iso_code": iso_code, "flag": flag})
    return team


def import_openfootball_snapshot(snapshot: DataSnapshot) -> int:
    data = json.loads(snapshot.payload)
    updated = 0
    for index, record in enumerate(data.get("matches", []), start=1):
        match_number = int(record.get("num") or record.get("match") or index)
        venue, _ = Venue.objects.get_or_create(name=record.get("ground") or "TBD")
        home_label = record.get("team1") or record.get("home") or "TBD"
        away_label = record.get("team2") or record.get("away") or "TBD"
        home_team = get_or_create_team(home_label)
        away_team = get_or_create_team(away_label)
        kickoff_at = parse_openfootball_datetime(record.get("date"), record.get("time", "00:00"))
        score1 = record.get("score1")
        score2 = record.get("score2")
        status = Match.Status.FINAL if score1 is not None and score2 is not None else Match.Status.SCHEDULED
        Match.objects.update_or_create(
            match_number=match_number,
            defaults={
                "stage": stage_from_record(record),
                "group": record.get("group") or "",
                "round_label": record.get("round") or "",
                "kickoff_at": kickoff_at,
                "venue": venue,
                "home_team": home_team,
                "away_team": away_team,
                "home_label": home_label,
                "away_label": away_label,
                "status": status,
                "home_score": score1,
                "away_score": score2,
                "source_payload": record,
            },
        )
        updated += 1
    snapshot.parsed_ok = True
    snapshot.parse_message = f"Imported {updated} matches from OpenFootball."
    snapshot.save(update_fields=["parsed_ok", "parse_message"])
    return updated


def import_default_sources(openfootball_file: str | None = None, skip_remote_fifa: bool = False) -> dict:
    details = {"snapshots": []}
    if not skip_remote_fifa:
        for source, url in (
            (DataSnapshot.Source.FIFA_SCHEDULE, settings.FANTASY_FIFA_SCHEDULE_URL),
            (DataSnapshot.Source.FIFA_SCORES, settings.FANTASY_FIFA_SCORES_URL),
        ):
            snapshot = load_payload(source, url=url)
            details["snapshots"].append(snapshot.id)
    openfootball = load_payload(
        DataSnapshot.Source.OPENFOOTBALL,
        url=settings.FANTASY_OPENFOOTBALL_URL if not openfootball_file else None,
        file_path=openfootball_file,
    )
    details["snapshots"].append(openfootball.id)
    updated = import_openfootball_snapshot(openfootball)
    details["updated"] = updated
    return details


def sync_scores_from_openfootball(openfootball_file: str | None = None) -> dict:
    snapshot = load_payload(
        DataSnapshot.Source.OPENFOOTBALL,
        url=settings.FANTASY_OPENFOOTBALL_URL if not openfootball_file else None,
        file_path=openfootball_file,
    )
    data = json.loads(snapshot.payload)
    updated = 0
    conflicts = []
    by_number = {match.match_number: match for match in Match.objects.all()}
    for index, record in enumerate(data.get("matches", []), start=1):
        match_number = int(record.get("num") or record.get("match") or index)
        score1 = record.get("score1")
        score2 = record.get("score2")
        if score1 is None or score2 is None or match_number not in by_number:
            continue
        match = by_number[match_number]
        incoming = (int(score1), int(score2))
        existing = (match.home_score, match.away_score)
        if match.is_scored and existing != incoming:
            conflicts.append({"match": match_number, "existing": existing, "incoming": incoming})
            continue
        match.home_score = incoming[0]
        match.away_score = incoming[1]
        match.status = Match.Status.FINAL
        match.save(update_fields=["home_score", "away_score", "status", "updated_at"])
        updated += 1
    snapshot.parsed_ok = True
    snapshot.parse_message = f"Score sync updated {updated} matches with {len(conflicts)} conflicts."
    snapshot.save(update_fields=["parsed_ok", "parse_message"])
    return {"updated": updated, "conflicts": conflicts, "snapshot": snapshot.id}
