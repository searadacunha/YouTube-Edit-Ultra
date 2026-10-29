"""Describe and validate a sport-first montage without an online AI dependency."""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


SPORT_PRESETS: dict[str, dict[str, float]] = {
    # Amount of context before impact and after the resolution, in seconds.
    "boxing": {"lead": 7.0, "trail": 8.0, "min_event": 6.0},
    "football": {"lead": 11.0, "trail": 15.0, "min_event": 8.0},
    "mma": {"lead": 8.0, "trail": 12.0, "min_event": 7.0},
    "basketball": {"lead": 6.0, "trail": 9.0, "min_event": 5.0},
    "generic": {"lead": 7.0, "trail": 8.0, "min_event": 6.0},
}
ATHLETE_SPORT = {
    "ronaldo": "football", "quaresma": "football", "haaland": "football",
    "goncalves": "football", "messi": "football", "neymar": "football",
    "crawford": "boxing", "tyson": "boxing", "mayweather": "boxing", "inoue": "boxing",
    "maidana": "boxing", "valero": "boxing", "canelo": "boxing",
    "muratalla": "boxing", "da cunha": "boxing", "duran": "boxing",
}
STYLE_KEYS = {
    "orchestral": "orchestral", "classical": "classical",
    "funk": "funk-brasileiro", "funk do brasil": "funk-brasileiro",
    "r&b 2000s": "rnb-2000s", "rnb 2000s": "rnb-2000s", "r&b": "rnb", "reggaeton": "reggaeton", "hip hop": "hip-hop", "hip-hop": "hip-hop",
    "rap us": "hip-hop", "trap": "trap", "j-pop": "j-pop",
    "jpop": "j-pop", "punk rock": "punk-rock", "rock": "rock",
    "juice wrld": "juice-wrld", "phonk": "phonk", "electro": "electronic",
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value).strip()


def parse_duration(value: str | int | float) -> float:
    """Parse 30min, 30 mn, 1h15, 90s, or a numerical number of minutes."""
    if isinstance(value, (int, float)):
        return float(value) * 60
    s = normalize(str(value)).strip()
    if not s:
        raise ValueError("Durée vide")
    compact = re.fullmatch(r"(\d+)h(\d{1,2})", s)
    if compact:
        return int(compact.group(1)) * 3600 + int(compact.group(2)) * 60
    h = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:heures?|h)(?=\d|\s|$)", s)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m|mn|min|minutes?)\b", s)
    sec = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:s|sec|secondes?)\b", s)
    if h or m or sec:
        return (float(h.group(1).replace(",", ".")) * 3600 if h else 0) + (float(m.group(1).replace(",", ".")) * 60 if m else 0) + (float(sec.group(1).replace(",", ".")) if sec else 0)
    if re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        return float(s.replace(",", ".")) * 60
    raise ValueError(f"Durée non reconnue : {value!r}")


def detect_style(prompt: str) -> str:
    s = normalize(prompt)
    for k in sorted(STYLE_KEYS, key=len, reverse=True):
        if k in s:
            return STYLE_KEYS[k]
    return "default"


def detect_sport(prompt: str) -> str:
    s = normalize(prompt)
    for k, v in ATHLETE_SPORT.items():
        if k in s:
            return v
    if re.search(r"\b(boxe|boxing|ko|punch|combat)\b", s):
        return "boxing"
    if re.search(r"\b(foot|football|soccer|buts?|dribbles?)\b", s):
        return "football"
    return "generic"


def detect_athlete(prompt: str) -> str:
    for name in ("Cristiano Ronaldo", "Ricardo Quaresma", "Erling Haaland", "Flavio Goncalves",
                 "Terence Crawford", "Mike Tyson", "Floyd Mayweather", "Naoya Inoue", "Marcos Maidana",
                 "Edwin Valero", "Benjamin Da Cunha", "Raymond Muratalla", "Canelo Alvarez",
                 "Lionel Messi", "Neymar"):
        if normalize(name) in normalize(prompt):
            return name
    for key in sorted(ATHLETE_SPORT, key=len, reverse=True):
        if re.search(r"\b" + re.escape(key) + r"\b", normalize(prompt)):
            return key.title()
    match = re.search(r"(?:de|sur|avec|montage|mix|highlights)\s+([\wÀ-ÿ][\wÀ-ÿ .'-]{2,60}?)(?:\s+\d+\s*(?:h|m)|\s+(?:avec|sur|en|musique|style)|[,;.\n]|$)", prompt, re.I)
    if match:
        return match.group(1).strip()
    # The documented one-prompt syntax also accepts subjects outside the presets.
    match = PROMPT_DURATION.search(normalize(prompt))
    if match:
        subject = normalize(prompt)[:match.start()].strip(" ,:-")
        if subject and re.fullmatch(r"[\w .'-]+", subject):
            return subject.title()
    return "Sport highlights"


# Hours with compact minutes (e.g. 1h15) must be captured as one duration.
# Otherwise parse_duration() never sees them and silently falls back to 5 minutes.
PROMPT_DURATION = re.compile(
    r"(?<!\w)\d+(?:[.,]\d+)?\s*"
    r"(?:h(?:eures?)?(?:\s*\d{1,2}\s*(?:m(?:n|in(?:utes?)?)?)?)?|"
    r"m(?:n|in(?:utes?)?)?|s(?:ec(?:ondes?)?)?)\b"
)


def parse_prompt(prompt: str) -> dict[str, Any]:
    found = PROMPT_DURATION.search(normalize(prompt))
    return {
        "athlete": detect_athlete(prompt),
        "sport": detect_sport(prompt),
        "style": detect_style(prompt),
        "duration_seconds": parse_duration(found.group()) if found else 300,
    }


@dataclass
class Settings:
    athlete: str
    sport: str
    style: str
    duration_seconds: float
    output: Path
    library: Path
    allow_download: bool = False
    allow_repeat: bool = False
    allow_music_repeat: bool = False
    publish: str = "none"
    width: int = 1280
    height: int = 720
    fps: int = 30
    source_volume: float = 0.22
    music_volume: float = 0.86
    scene_detect: bool = False
    annotation_paths: list[Path] = field(default_factory=list)
    video_sources: list[str] = field(default_factory=list)
    music_paths: list[Path] = field(default_factory=list)
    title: str | None = None
    created_from: str = ""

    def __post_init__(self) -> None:
        if self.sport not in SPORT_PRESETS:
            raise ValueError(f"Sport inconnu: {self.sport}")
        if (type(self.duration_seconds) not in (int, float)
                or not math.isfinite(self.duration_seconds)
                or not 0 < self.duration_seconds <= 4 * 3600):
            raise ValueError("Durée requise comprise entre 1 seconde et 4 heures")
        if self.publish not in {"none", "private", "unlisted", "public"}:
            raise ValueError("Statut YouTube non valide")
        if (type(self.width) is not int or type(self.height) is not int
                or self.width <= 0 or self.height <= 0
                or self.width % 2 or self.height % 2):
            raise ValueError("Résolution positive et paire requise pour H.264")
        if type(self.fps) is not int or self.fps <= 0:
            raise ValueError("FPS doit être un entier positif")


def load_manifest(path: Path) -> dict[str, Any]:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        raise ValueError("Le manifeste YAML doit être un objet")
    return content
