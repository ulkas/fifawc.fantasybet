from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.request import Request, urlopen
import ssl

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
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            return FetchResult(raw.decode("utf-8", errors="replace"), response.headers.get("Content-Type", ""))
    except Exception as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, ssl.SSLError) or (hasattr(reason, "args") and any(isinstance(a, ssl.SSLError) for a in getattr(reason, "args", []))):
            # Retry with an unverified SSL context for environments missing CA bundles
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urlopen(request, timeout=30, context=ctx) as response:
                raw = response.read()
                return FetchResult(raw.decode("utf-8", errors="replace"), response.headers.get("Content-Type", ""))
        raise


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
        url=("https://worldcup26.ir/get/games" if not openfootball_file else None),
        file_path=openfootball_file,
    )

    def _to_int(value):
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _parse_kickoff(value) -> datetime | None:
        if not value:
            return None
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(int(value), dt_timezone.utc)
            except Exception:
                return None
        try:
            # Accept full ISO datetimes or date strings
            dt = datetime.fromisoformat(str(value))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_timezone.utc)
            return dt.astimezone(dt_timezone.utc)
        except Exception:
            return None

    def _map_status(s: str) -> str:
        if not s:
            return Match.Status.SCHEDULED
        s_norm = str(s).strip().lower()
        if any(tok in s_norm for tok in ("ft", "final", "finished", "full")):
            return Match.Status.FINAL
        if any(tok in s_norm for tok in ("live", "inplay", "in play", "ongoing", "started", "second half", "first half", "ht")):
            return Match.Status.LIVE
        if "postpon" in s_norm:
            return Match.Status.POSTPONED
        return Match.Status.SCHEDULED

    def _extract_field(obj: dict, candidates: list):
        for key in candidates:
            if key in obj and obj.get(key) not in (None, ""):
                return obj.get(key)
        return None

    def parse_worldcup26_matches(payload_text: str) -> list:
        try:
            data = json.loads(payload_text)
        except Exception as exc:
            raise ValueError(f"Invalid JSON payload: {exc}") from exc

        # payload may be a dict with top-level keys or a list
        items = []
        if isinstance(data, dict):
            # common keys
            if "games" in data:
                items = data.get("games") or []
            elif "matches" in data:
                items = data.get("matches") or []
            elif "data" in data and isinstance(data.get("data"), list):
                items = data.get("data")
            else:
                # defensive: if dict looks like a single match, wrap it
                # otherwise try to find any list value
                for v in data.values():
                    if isinstance(v, list):
                        items = v
                        break
                if not items:
                    raise ValueError("Payload JSON does not contain a list of matches/games")
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError("Unexpected payload shape for WorldCup26 data")

        normalized = []
        for obj in items:
            if not isinstance(obj, dict):
                continue
            # identifier candidates
            ident = _extract_field(obj, ["match", "num", "id", "game_id", "gid", "match_number"])
            match_number = _to_int(ident)

            # team name candidates
            home_label = _extract_field(obj, ["home_team_name_en", "home_team", "home", "team1", "team1_name", "home_name", "homeTeam", "homeTeamName"]) or ""
            away_label = _extract_field(obj, ["away_team_name_en", "away_team", "away", "team2", "team2_name", "away_name", "awayTeam", "awayTeamName"]) or ""

            # scores
            home_score = _to_int(_extract_field(obj, ["home_score", "score1", "score_home", "homeGoals", "home_goals"]))
            away_score = _to_int(_extract_field(obj, ["away_score", "score2", "score_away", "awayGoals", "away_goals"]))

            # status
            status_raw = _extract_field(obj, ["status", "state", "match_status", "stage", "finished", "time_elapsed"]) or ""
            status = _map_status(status_raw)

            # kickoff
            kickoff_raw = _extract_field(obj, ["datetime", "kickoff", "kickoff_at", "date_time", "date", "time"]) or _extract_field(obj, ["utcDate", "dateUtc"]) or None
            kickoff = _parse_kickoff(kickoff_raw)

            normalized.append({
                "match_number": match_number,
                "home_label": str(home_label).strip(),
                "away_label": str(away_label).strip(),
                "home_score": home_score,
                "away_score": away_score,
                "status": status,
                "kickoff": kickoff,
                "raw": obj,
            })

        return normalized

    # parse payload
    try:
        records = parse_worldcup26_matches(snapshot.payload)
    except Exception as exc:
        snapshot.parsed_ok = False
        snapshot.parse_message = f"Failed to parse WorldCup26 payload: {exc}"
        snapshot.save(update_fields=["parsed_ok", "parse_message"])
        raise

    updated = 0
    conflicts = []

    matches = list(Match.objects.all())
    by_number = {m.match_number: m for m in matches}
    by_labels: dict[tuple, list] = {}
    for m in matches:
        key = (m.home_label.strip().lower(), m.away_label.strip().lower())
        by_labels.setdefault(key, []).append(m)

    for rec in records:
        match_obj = None
        # prefer numeric match_number but validate by team labels/kickoff
        if rec.get("match_number") and rec["match_number"] in by_number:
            candidate = by_number[rec["match_number"]]
            # validate label match (loose)
            can_home = (candidate.home_label or "").strip().lower()
            can_away = (candidate.away_label or "").strip().lower()
            rec_home = (rec.get("home_label") or "").strip().lower()
            rec_away = (rec.get("away_label") or "").strip().lower()
            labels_match = (rec_home and rec_away and rec_home == can_home and rec_away == can_away)
            # allow minor variations: check substring inclusion
            labels_similar = (rec_home and rec_away and rec_home in can_home and rec_away in can_away) or (rec_home and rec_away and can_home in rec_home and can_away in rec_away)
            kickoff_ok = False
            try:
                if rec.get("kickoff") and candidate.kickoff_at:
                    kickoff_ok = abs((candidate.kickoff_at - rec["kickoff"]).total_seconds()) < 60 * 60 * 6
            except Exception:
                kickoff_ok = False

            if labels_match or labels_similar or kickoff_ok:
                match_obj = candidate
            else:
                match_obj = None

        # fallback to label matching
        if not match_obj:
            key = (rec["home_label"].lower(), rec["away_label"].lower())
            candidates = by_labels.get(key, [])
            if len(candidates) == 1:
                match_obj = candidates[0]
            elif len(candidates) > 1 and rec.get("kickoff"):
                # try to disambiguate by kickoff time (within 6 hours)
                for cand in candidates:
                    try:
                        if cand.kickoff_at and abs((cand.kickoff_at - rec["kickoff"]).total_seconds()) < 60 * 60 * 6:
                            match_obj = cand
                            break
                    except Exception:
                        continue

        if not match_obj:
            # cannot confidently match, skip
            continue

        # only update when numeric scores available
        home_score = rec.get("home_score")
        away_score = rec.get("away_score")
        parsed_status = rec.get("status")

        # If numeric scores available, update DB with incoming values.
        # Only mark the match FINAL when the incoming status indicates a finished match.
        if home_score is not None and away_score is not None:
            incoming = (int(home_score), int(away_score))
            match_obj.home_score = incoming[0]
            match_obj.away_score = incoming[1]
            match_obj.source_payload = rec.get("raw") or {}
            # Only transition to FINAL when source reports a finished match.
            if parsed_status == Match.Status.FINAL:
                match_obj.status = Match.Status.FINAL
            elif parsed_status == Match.Status.LIVE:
                match_obj.status = Match.Status.LIVE
            # otherwise leave the existing status (e.g. scheduled) untouched
            match_obj.save(update_fields=["home_score", "away_score", "status", "source_payload", "updated_at"])
            updated += 1
        else:
            # no numeric scores; update status to LIVE if indicated
            if parsed_status == Match.Status.LIVE and match_obj.status != Match.Status.LIVE:
                match_obj.status = Match.Status.LIVE
                match_obj.source_payload = rec.get("raw") or {}
                match_obj.save(update_fields=["status", "source_payload", "updated_at"])

    snapshot.parsed_ok = True
    snapshot.parse_message = f"Score sync processed {len(records)} records, updated {updated} matches with {len(conflicts)} conflicts."
    snapshot.save(update_fields=["parsed_ok", "parse_message"])
    return {"updated": updated, "conflicts": conflicts, "snapshot": snapshot.id}
