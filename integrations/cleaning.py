"""Small functions that turn messy source values into clean ones.

Each function either returns a clean value or raises CleaningError with a reason the
person fixing the data can understand. They never guess: a value they don't recognise
is rejected rather than silently changed.
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class CleaningError(ValueError):
    """A value that can't be cleaned; the message says why."""


def clean_text(value):
    """Trim and collapse repeated spaces. Missing values become an empty string."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _key(value):
    """Lower-case letters and digits only, for matching spelling variants."""
    return re.sub(r"[^a-z0-9]", "", clean_text(value).lower())


# Day first, as dates are written in Uganda.
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y",
                "%Y/%m/%d"]


def parse_date(value, field="date"):
    """Read a date written in any of the common formats; reject anything else."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        raise CleaningError(f"{field} is missing")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise CleaningError(f"{field} '{text}' is not a recognised date")


def _lookup(value, synonyms, field):
    """Find a value's clean code from a {code: [spellings]} table."""
    key = _key(value)
    if not key:
        raise CleaningError(f"{field} is missing")
    for code, spellings in synonyms.items():
        if key in {_key(s) for s in spellings}:
            return code
    raise CleaningError(f"{field} '{clean_text(value)}' is not recognised")


GENDERS = {
    "male": ["m", "male", "boy", "b"],
    "female": ["f", "female", "girl", "g"],
}


def normalise_gender(value):
    """'M', 'Male', 'boy' → 'male'; 'F', 'Female', 'girl' → 'female'."""
    return _lookup(value, GENDERS, "gender")


CAMPUSES = {
    "kibuli": ["kibuli", "kibuli main", "kibuli main campus", "kibuli campus", "kbl"],
    "buwaate": ["buwaate", "buwaate campus", "buwate", "bwt"],
    "annex": ["annex", "annex preschool", "annex / preschool branch", "preschool branch",
              "annex campus"],
}


def normalise_campus(value):
    """'KIBULI MAIN ', 'Kibuli Main Campus' → 'kibuli'; likewise 'buwaate' and 'annex'."""
    return _lookup(value, CAMPUSES, "campus")


NATIONALITIES = {
    "Ugandan": ["ug", "uga", "uganda", "ugandan"],
    "Kenyan": ["ke", "ken", "kenya", "kenyan"],
    "Rwandese": ["rw", "rwa", "rwanda", "rwandan", "rwandese"],
    "South Sudanese": ["ss", "ssd", "south sudan", "south sudanese"],
    "Tanzanian": ["tz", "tza", "tanzania", "tanzanian"],
    "Congolese": ["cd", "cod", "drc", "congo", "congolese"],
    "Burundian": ["bi", "bdi", "burundi", "burundian"],
}


def normalise_nationality(value):
    """Country codes and names become one spelling, e.g. 'UG' and 'uganda' → 'Ugandan'.
    Nationalities not in the table are kept, written in title case."""
    try:
        return _lookup(value, NATIONALITIES, "nationality")
    except CleaningError:
        text = clean_text(value)
        if not text:
            raise
        return text.title()


def parse_term_number(value):
    """'Term 3', 'T3', 'III' or 3 → 3. Only terms 1 to 3 exist."""
    text = clean_text(value).upper()
    roman = {"I": 1, "II": 2, "III": 3}
    match = re.fullmatch(r"(?:TERM|T)?\s*(\d|I{1,3})", text)
    if match:
        part = match.group(1)
        number = roman.get(part) or int(part)
        if 1 <= number <= 3:
            return number
    raise CleaningError(f"term '{clean_text(value)}' is not a term from 1 to 3")


def map_choice(value, synonyms, field, default=None):
    """Map a source value onto one of our codes using a {code: [spellings]} table.
    Unrecognised values become `default` when one is given, otherwise they're rejected."""
    try:
        return _lookup(value, synonyms, field)
    except CleaningError:
        if default is not None and clean_text(value):
            return default
        raise


def parse_money(value, field="amount"):
    """'UGX 1,500,000', '1,500,000.00' or 1500000 → Decimal('1500000.00'). Rejects
    negative or unreadable amounts."""
    text = re.sub(r"(?i)\b(ugx|ush|shs)\b|[,\s]", "", clean_text(value))
    if not text:
        raise CleaningError(f"{field} is missing")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise CleaningError(f"{field} '{clean_text(value)}' is not an amount") from None
    if amount < 0:
        raise CleaningError(f"{field} '{clean_text(value)}' is negative")
    return amount.quantize(Decimal("0.01"))
