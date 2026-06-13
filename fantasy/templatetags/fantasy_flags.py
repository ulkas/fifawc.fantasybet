from __future__ import annotations

from django import template

register = template.Library()


FLAG_CODES_BY_NAME = {
    "Algeria": "dz",
    "Argentina": "ar",
    "Australia": "au",
    "Austria": "at",
    "Belgium": "be",
    "Bosnia & Herzegovina": "ba",
    "Bosnia and Herzegovina": "ba",
    "Brazil": "br",
    "Canada": "ca",
    "Cape Verde": "cv",
    "Colombia": "co",
    "Croatia": "hr",
    "Curacao": "cw",
    "Curaçao": "cw",
    "Czech Republic": "cz",
    "DR Congo": "cd",
    "Ecuador": "ec",
    "Egypt": "eg",
    "England": "gb-eng",
    "France": "fr",
    "Germany": "de",
    "Ghana": "gh",
    "Haiti": "ht",
    "Iran": "ir",
    "IR Iran": "ir",
    "Iraq": "iq",
    "Ivory Coast": "ci",
    "Cote d'Ivoire": "ci",
    "Japan": "jp",
    "Jordan": "jo",
    "Mexico": "mx",
    "Morocco": "ma",
    "Netherlands": "nl",
    "New Zealand": "nz",
    "Norway": "no",
    "Panama": "pa",
    "Paraguay": "py",
    "Portugal": "pt",
    "Qatar": "qa",
    "Saudi Arabia": "sa",
    "Scotland": "gb-sct",
    "Senegal": "sn",
    "South Africa": "za",
    "South Korea": "kr",
    "Spain": "es",
    "Sweden": "se",
    "Switzerland": "ch",
    "Tunisia": "tn",
    "Turkey": "tr",
    "USA": "us",
    "Uruguay": "uy",
    "Uzbekistan": "uz",
}


@register.inclusion_tag("fantasy/partials/flag_image.html")
def flag_image(team, label: str = ""):
    name = getattr(team, "name", "") or label
    code = FLAG_CODES_BY_NAME.get(name, "")
    return {"code": code, "name": name}
