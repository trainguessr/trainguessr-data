from __future__ import annotations

import re
import unicodedata


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.upper().replace("&", " E ")
    return re.sub(r"[^A-Z0-9]+", " ", value).strip()
