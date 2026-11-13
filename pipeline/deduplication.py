"""Conservative publication deduplication: only identical nonempty DOIs merge."""
import re

def normalize_doi(value):
    value = (value or "").strip()
    value = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^https://link\.springer\.com/book/", "", value, flags=re.I)
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    return value.strip().lower()

def duplicate_key(entry):
    doi = normalize_doi(entry.get("doi", ""))
    return "doi:" + doi if re.fullmatch(r'10\.\d{4,9}/\S+', doi) else None
