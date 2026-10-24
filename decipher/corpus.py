"""Shared source record and Unicode normalization for word-aligned glossing."""
from dataclasses import dataclass
import unicodedata


def nfc(text):
    return unicodedata.normalize('NFC', text)


@dataclass(frozen=True)
class TextExample:
    id: str
    tokens: tuple[str, ...]
