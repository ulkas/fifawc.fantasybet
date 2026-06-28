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
    "South Korea": ("KOR", flag_emoji("KR")),
    "Bosnia and Herzegovina": ("BIH", flag_emoji("BA")),
    "Paraguay": ("PAR", flag_emoji("PY")),
    "Haiti": ("HAI", flag_emoji("HT")),
    "Turkey": ("TUR", flag_emoji("TR")),
    "Qatar": ("QAT", flag_emoji("QA")),
    "CuraÃƒÂ§ao": ("CUR", flag_emoji("CW")),
    "Ivory Coast": ("CIV", flag_emoji("CI")),
    "Cape Verde": ("CPV", flag_emoji("CV")),
    "Democratic Republic of the Congo": ("COD", flag_emoji("CD")),
    "Sweden": ("SWE", flag_emoji("SE")),
    "Norway": ("NOR", flag_emoji("NO")),
    "Iraq": ("IRQ", flag_emoji("IQ")),
    "Senegal": ("SEN", flag_emoji("SN")),
    "Austria": ("AUT", flag_emoji("AT")),
    "Jordan": ("JOR", flag_emoji("JO")),
    "Uzbekistan": ("UZB", flag_emoji("UZ")),
    "Colombia": ("COL", flag_emoji("CO")),
    "Panama": ("PAN", flag_emoji("PA")),
    "Algeria": ("ALG", flag_emoji("DZ")),
    "Croatia": ("CRO", flag_emoji("HR")),
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
            dt = datetime.fromisoformat(str(value))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_timezone.utc)
            return dt.astimezone(dt_timezone.utc)
        except Exception:
            s = str(value).strip()
            patterns = ["%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]
            for p in patterns:
                try:
                    dt = datetime.strptime(s, p)
                    dt = dt.replace(tzinfo=dt_timezone.utc)
                    return dt.astimezone(dt_timezone.utc)
                except Exception:
                    continue
            return None

    def _map_status(s: str) -> str:
        if not s:
            return Match.Status.SCHEDULED
        if isinstance(s, bool):
            return Match.Status.FINAL if s else Match.Status.SCHEDULED
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

    LABEL_ALIASES = {
        "united states": "USA",
        "united states of america": "USA",
        "us": "USA",
        "u.s.": "USA",
        "u.s.a.": "USA",
    }
    LABEL_ALIASES.update({
        "democratic republic of the congo": "DR Congo",
        "democratic republic of congo": "DR Congo",
        "dr congo": "DR Congo",
        "d.r. congo": "DR Congo",
        "congo dr": "DR Congo",
        "congo, dr": "DR Congo",
        "ivory coast": "Ivory Coast",
        "cote d'ivoire": "Ivory Coast",
        "cÃƒÂ´te d'ivoire": "Ivory Coast",
    })
    LABEL_ALIASES.update({
        "bosnia & herzegovina": "Bosnia and Herzegovina",
        "bosnia and herzegovina": "Bosnia and Herzegovina",
    })

    def _normalize_placeholder_label(label: str) -> str:
        clean = re.sub(r"\s+", " ", str(label or "").strip().lower())
        if not clean:
            return ""
        clean = re.sub(r"\s*/\s*", "/", clean)

        direct_patterns = (
            (r"^1([a-z])$", "1{}"),
            (r"^2([a-z])$", "2{}"),
            (r"^3([a-z](?:/[a-z])*)$", "3{}"),
        )
        for pattern, template in direct_patterns:
            match = re.match(pattern, clean)
            if match:
                return template.format(match.group(1).upper())

        named_patterns = (
            (r"^(?:winner|group winner)\s+group\s+([a-z])$", "1{}"),
            (r"^(?:runner-up|runner up|group runner-up|group runner up)\s+group\s+([a-z])$", "2{}"),
            (r"^(?:3rd|third)\s+group\s+([a-z](?:/[a-z])*)$", "3{}"),
        )
        for pattern, template in named_patterns:
            match = re.match(pattern, clean)
            if match:
                return template.format(match.group(1).upper())

        return clean

    def _normalize_label(label: str) -> str:
        if not label:
            return ""
        key = str(label).strip()
        placeholder_key = _normalize_placeholder_label(key)
        if placeholder_key and placeholder_key != key.lower():
            return placeholder_key
        key_low = key.lower()
        if key_low in LABEL_ALIASES:
            return LABEL_ALIASES[key_low]
        if key_low == "usa":
            return "USA"
        return key

    def _normalized_key(label: str) -> str:
        return _normalize_label(label).strip().lower()

    def _candidate_label_keys(*labels: str) -> set[str]:
        keys = set()
        for label in labels:
            key = _normalized_key(label)
            if key:
                keys.add(key)
        return keys

    def _display_label(name_label: str, placeholder_label: str) -> str:
        return (name_label or placeholder_label or "").strip()

    def _match_label_keys(match_obj: Match, side: str) -> set[str]:
        source_payload = match_obj.source_payload or {}
        current_label = getattr(match_obj, f"{side}_label", "")
        team_obj = getattr(match_obj, f"{side}_team", None)
        payload_name = source_payload.get(f"{side}_team_name_en", "")
        payload_placeholder = source_payload.get(f"{side}_team_label", "")
        team_name = team_obj.name if team_obj else ""
        return _candidate_label_keys(current_label, team_name, payload_name, payload_placeholder)

    def _record_label_keys(record: dict, side: str) -> set[str]:
        return _candidate_label_keys(
            record.get(f"{side}_label", ""),
            record.get(f"{side}_placeholder_label", ""),
        )

    def _group_key(value: str) -> str:
        clean = str(value or "").strip().lower()
        if clean.startswith("group "):
            clean = clean.removeprefix("group ").strip()
        return clean

    def parse_worldcup26_matches(payload_text: str) -> list:
        try:
            data = json.loads(payload_text)
        except Exception as exc:
            raise ValueError(f"Invalid JSON payload: {exc}") from exc

        items = []
        if isinstance(data, dict):
            if "games" in data:
                items = data.get("games") or []
            elif "matches" in data:
                items = data.get("matches") or []
            elif "data" in data and isinstance(data.get("data"), list):
                items = data.get("data")
            else:
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
            ident = _extract_field(obj, ["match", "num", "id", "game_id", "gid", "match_number"])
            match_number = _to_int(ident)

            home_name = _normalize_label(_extract_field(obj, ["home_team_name_en", "home_team", "home", "team1", "team1_name", "home_name", "homeTeam", "homeTeamName"]) or "")
            away_name = _normalize_label(_extract_field(obj, ["away_team_name_en", "away_team", "away", "team2", "team2_name", "away_name", "awayTeam", "awayTeamName"]) or "")
            home_placeholder = str(_extract_field(obj, ["home_team_label", "home_label"]) or "").strip()
            away_placeholder = str(_extract_field(obj, ["away_team_label", "away_label"]) or "").strip()
            home_label = _display_label(home_name, home_placeholder)
            away_label = _display_label(away_name, away_placeholder)

            home_score = _to_int(_extract_field(obj, ["home_score", "score1", "score_home", "homeGoals", "home_goals"]))
            away_score = _to_int(_extract_field(obj, ["away_score", "score2", "score_away", "awayGoals", "away_goals"]))

            status_raw = _extract_field(obj, ["status", "state", "match_status", "stage", "finished", "time_elapsed"]) or ""
            finished_flag = None
            if "finished" in obj:
                val = obj.get("finished")
                if isinstance(val, bool):
                    finished_flag = val
                else:
                    try:
                        if int(val) != 0:
                            finished_flag = True
                    except Exception:
                        if str(val).strip().lower() in ("true", "yes", "1"):
                            finished_flag = True
            if finished_flag is True:
                status = Match.Status.FINAL
            elif not status_raw and home_score is not None and away_score is not None:
                status = Match.Status.FINAL
            else:
                status = _map_status(status_raw)

            kickoff_raw = _extract_field(obj, ["datetime", "kickoff", "kickoff_at", "date_time", "date", "time", "local_date"]) or _extract_field(obj, ["utcDate", "dateUtc"]) or None
            kickoff = _parse_kickoff(kickoff_raw)

            normalized.append({
                "match_number": match_number,
                "home_label": home_label,
                "away_label": away_label,
                "home_placeholder_label": home_placeholder,
                "away_placeholder_label": away_placeholder,
                "home_name_label": home_name,
                "away_name_label": away_name,
                "group": str(obj.get("group") or "").strip(),
                "type": str(obj.get("type") or "").strip().lower(),
                "home_score": home_score,
                "away_score": away_score,
                "status": status,
                "kickoff": kickoff,
                "raw": obj,
            })

        return normalized

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

    for rec in records:
        match_obj = None
        is_group_record = rec.get("type") == "group" or len(_group_key(rec.get("group", ""))) == 1
        if not is_group_record and rec.get("match_number") and rec["match_number"] in by_number:
            candidate = by_number[rec["match_number"]]
            candidate_home_keys = _match_label_keys(candidate, "home")
            candidate_away_keys = _match_label_keys(candidate, "away")
            record_home_keys = _record_label_keys(rec, "home")
            record_away_keys = _record_label_keys(rec, "away")
            labels_match = (
                (not record_home_keys or bool(record_home_keys & candidate_home_keys))
                and (not record_away_keys or bool(record_away_keys & candidate_away_keys))
            )
            kickoff_ok = False
            try:
                if rec.get("kickoff") and candidate.kickoff_at:
                    kickoff_ok = abs((candidate.kickoff_at - rec["kickoff"]).total_seconds()) < 60 * 60 * 6
            except Exception:
                kickoff_ok = False

            if labels_match or (kickoff_ok and not (record_home_keys or record_away_keys)):
                match_obj = candidate

        if not match_obj:
            record_home_keys = _record_label_keys(rec, "home")
            record_away_keys = _record_label_keys(rec, "away")
            for cand in matches:
                candidate_home_keys = _match_label_keys(cand, "home")
                candidate_away_keys = _match_label_keys(cand, "away")
                labels_match = (
                    (not record_home_keys or bool(record_home_keys & candidate_home_keys))
                    and (not record_away_keys or bool(record_away_keys & candidate_away_keys))
                )
                kickoff_ok = False
                try:
                    if rec.get("kickoff") and cand.kickoff_at:
                        kickoff_ok = abs((cand.kickoff_at - rec["kickoff"]).total_seconds()) < 60 * 60 * 6
                except Exception:
                    kickoff_ok = False
                same_group = _group_key(rec.get("group", "")) == _group_key(cand.group)
                if labels_match and (kickoff_ok or same_group or not rec.get("kickoff")):
                    match_obj = cand
                    break

        if not match_obj:
            continue

        home_label = _display_label(rec.get("home_name_label", ""), rec.get("home_placeholder_label", ""))
        away_label = _display_label(rec.get("away_name_label", ""), rec.get("away_placeholder_label", ""))
        home_team = get_or_create_team(rec.get("home_name_label", ""))
        away_team = get_or_create_team(rec.get("away_name_label", ""))
        match_obj.home_label = home_label or match_obj.home_label
        match_obj.away_label = away_label or match_obj.away_label
        match_obj.home_team = home_team
        match_obj.away_team = away_team

        home_score = rec.get("home_score")
        away_score = rec.get("away_score")
        parsed_status = rec.get("status")

        match_obj.source_payload = rec.get("raw") or {}
        update_fields = ["home_label", "away_label", "home_team", "away_team", "source_payload", "updated_at"]

        if home_score is not None and away_score is not None:
            incoming = (int(home_score), int(away_score))
            match_obj.home_score = incoming[0]
            match_obj.away_score = incoming[1]
            update_fields.extend(["home_score", "away_score"])
            if parsed_status == Match.Status.FINAL:
                match_obj.status = Match.Status.FINAL
                update_fields.append("status")
            elif parsed_status == Match.Status.LIVE:
                match_obj.status = Match.Status.LIVE
                update_fields.append("status")
            match_obj.save(update_fields=update_fields)
            updated += 1
        else:
            if parsed_status == Match.Status.LIVE and match_obj.status != Match.Status.LIVE:
                match_obj.status = Match.Status.LIVE
                update_fields.append("status")
            match_obj.save(update_fields=update_fields)

    snapshot.parsed_ok = True
    snapshot.parse_message = f"Score sync processed {len(records)} records, updated {updated} matches with {len(conflicts)} conflicts."
    snapshot.save(update_fields=["parsed_ok", "parse_message"])
    return {"updated": updated, "conflicts": conflicts, "snapshot": snapshot.id}




