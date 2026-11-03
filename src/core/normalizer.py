"""String normalization and lineup splitting logic for acts and reviews."""

import re
from typing import List, Set
from unidecode import unidecode

# Common prefixes to strip from event titles
EVENT_PREFIX_PATTERNS = [
    r"^an evening with\s+",
    r"^in conversation with\s+",
    r"^live:\s+",
    r"^presents:\s+",
    r"^album launch:\s+",
    r"^single launch:\s+",
]

# Suffixes and parentheticals to clean out
EVENT_SUFFIX_PATTERNS = [
    r"\s*[\(\[](live|dj\s*set|hybrid\s*set|matinee|single\s*launch|album\s*launch|sold\s*out|acoustic)[\)\]]",
    r"\s*[\(\[][^()]*tour[^()]*[\)\]]",
    r"\s*[\(\[][^()]*residency[^()]*[\)\]]",
    r"\s*[\(\[][^()]*party[^()]*[\)\]]",
]

# Lineup splitters (delimiters that separate distinct acts on a bill)
LINEUP_SPLIT_REGEX = re.compile(
    r"\s+(?:\+|\/|w\/|with|feat\.?|featuring|ft\.?|vs\.?|presents)\s+|\s*,\s*",
    re.IGNORECASE,
)

# Words that indicate generic support rather than an artist name
GENERIC_SUPPORT_TOKENS = {
    "special guests",
    "special guest",
    "support",
    "guests",
    "djs",
    "tba",
    "tbc",
    "plus guests",
    "plus special guests",
    "more to be announced",
    "and friends",
    "& friends",
}

# Artists with '&' or 'and' that should NOT be split across the ampersand
PROTECTED_AMPERSAND_ARTISTS = {
    "florence and the machine",
    "simon and garfunkel",
    "simon & garfunkel",
    "belle and sebastian",
    "belle & sebastian",
    "echo and the bunnymen",
    "echo & the bunnymen",
    "me first and the gimme gimmes",
    "king gizzard and the lizard wizard",
    "king gizzard & the lizard wizard",
    "black country, new road",
}


def normalize_artist_name(name: str) -> str:
    """
    Produce a canonical, punctuation-stripped, lowercase string for matching.
    
    Examples:
        'The Shacklewell Arms' -> 'shacklewell arms'
        'Beyoncé' -> 'beyonce'
        'Fontaines D.C. (Live)' -> 'fontaines dc'
        'Pond (Album Launch)' -> 'pond'
    """
    if not name:
        return ""

    text = name.strip()

    # 1. Clean event prefixes
    for prefix in EVENT_PREFIX_PATTERNS:
        text = re.sub(prefix, "", text, flags=re.IGNORECASE)

    # 2. Strip event suffixes/parentheticals
    for suffix in EVENT_SUFFIX_PATTERNS:
        text = re.sub(suffix, "", text, flags=re.IGNORECASE)

    # 3. Transliterate accents and diacritics (Beyoncé -> beyonce)
    text = unidecode(text).lower()

    # 4. Remove leading stop articles ("the ", "a ", "an ")
    text = re.sub(r"^(the|a|an)\s+", "", text)

    # 5. Remove punctuation except alphanumeric and spaces
    text = re.sub(r"[^\w\s]", "", text)

    # 6. Collapse multiple whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def split_lineup(event_title: str) -> List[str]:
    """
    Extract individual performing acts from a DICE event title.
    
    Example:
        'Pond + Warmduscher, Special Guests' -> ['Pond', 'Warmduscher']
        'An Evening with Lankum w/ Ethan P. Flynn' -> ['Lankum', 'Ethan P. Flynn']
    """
    if not event_title:
        return []

    cleaned_title = event_title.strip()

    # Remove event wrappers first
    for prefix in EVENT_PREFIX_PATTERNS:
        cleaned_title = re.sub(prefix, "", cleaned_title, flags=re.IGNORECASE)
    for suffix in EVENT_SUFFIX_PATTERNS:
        cleaned_title = re.sub(suffix, "", cleaned_title, flags=re.IGNORECASE)

    # Strip Songkick "@ Venue" or "at Venue" suffix
    if " @ " in cleaned_title:
        cleaned_title = cleaned_title.split(" @ ", 1)[0].strip()

    # Check if the title matches a known protected monolithic name
    normalized_whole = normalize_artist_name(cleaned_title)
    if normalized_whole in PROTECTED_AMPERSAND_ARTISTS:
        return [cleaned_title.strip()]

    # Split on lineup separators
    raw_parts = LINEUP_SPLIT_REGEX.split(cleaned_title)

    extracted_acts: List[str] = []
    for part in raw_parts:
        candidate = part.strip()
        norm = normalize_artist_name(candidate)

        # Skip empty strings or generic support placeholders
        if not norm or norm in GENERIC_SUPPORT_TOKENS:
            continue

        extracted_acts.append(candidate)

    # Fallback to the whole cleaned title if nothing extracted
    if not extracted_acts and cleaned_title:
        extracted_acts.append(cleaned_title)

    return extracted_acts


def extract_normalized_acts(event_title: str) -> List[str]:
    """Return the list of normalized act names for an event title."""
    acts = split_lineup(event_title)
    return [normalize_artist_name(act) for act in acts if normalize_artist_name(act)]


def matches_artist_set(
    event_normalized_acts: List[str],
    reference_normalized_set: Set[str]
) -> List[str]:
    """
    Return all acts from the event that match any artist in the reference set.
    """
    matches = []
    for act in event_normalized_acts:
        if act in reference_normalized_set:
            matches.append(act)
    return matches
