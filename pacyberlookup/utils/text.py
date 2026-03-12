"""Text normalization and matching utilities."""

import re
import unicodedata


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip extra whitespace, remove accents."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_entity_name(name: str) -> str:
    """Normalize an entity name for dedup key generation.

    Strips common suffixes and abbreviations to create a canonical form.
    """
    name = normalize_text(name)
    replacements = [
        (r"\btwp\.?\b", "township"),
        (r"\bboro\.?\b", "borough"),
        (r"\bmuni\.?\b", "municipality"),
        (r"\bauth\.?\b", "authority"),
        (r"\bdist\.?\b", "district"),
        (r"\bsd\b", "school district"),
        (r"\bdept\.?\b", "department"),
        (r"\bpd\b", "police department"),
    ]
    for pattern, replacement in replacements:
        name = re.sub(pattern, replacement, name)

    # Convert "township of X" -> "X township" (canonical form: name + type)
    m = re.match(r"^(township|borough|municipality) of (.+)", name)
    if m:
        name = f"{m.group(2)} {m.group(1)}"

    return re.sub(r"\s+", " ", name).strip()


def extract_incident_type(text: str) -> str | None:
    """Extract the most likely incident type from text."""
    text_lower = text.lower() if text else ""
    incident_types = [
        ("ransomware", ["ransomware"]),
        ("data breach", ["data breach", "breach notification", "data exposed"]),
        ("breach", ["breach", "unauthorized access", "compromised"]),
        ("phishing", ["phishing attack", "phishing"]),
        ("malware", ["malware", "network intrusion"]),
        ("outage", ["outage", "systems offline", "service interruption",
                     "network disruption", "systems disruption"]),
        ("cyberattack", ["cyberattack", "cyber attack", "cyber incident"]),
    ]
    for incident_type, keywords in incident_types:
        for kw in keywords:
            if kw in text_lower:
                return incident_type
    return None
