"""Tokens and scored words — NLP phase output types."""

from __future__ import annotations

from pydantic import Field

from aerocloud.models.base import AeroCloudBase


class Token(AeroCloudBase):
    """A single tokenized unit from the input text."""

    surface: str = Field(..., description="Original surface form as it appears in the text")
    stem: str = Field(..., description="Stemmed / lemmatized form used for counting")
    language: str = Field(..., description="ISO 639-1 code detected by franc / spaCy")
    is_stopword: bool = Field(default=False)


class ScoredWord(AeroCloudBase):
    """A token with its TF-IDF-AP score and positional weight contributions."""

    surface: str
    stem: str
    tf: float = Field(..., ge=0.0, description="Normalized term frequency")
    idf: float = Field(..., ge=0.0, description="Inverse document frequency")
    positional_weight: float = Field(default=1.0, ge=0.0, description="Title/H1 boost")
    score: float = Field(..., ge=0.0, description="tf * idf * positional_weight")


class WordCandidate(AeroCloudBase):
    """A scored word ready to be placed in the layout, with final font size."""

    surface: str
    stem: str
    score: float = Field(..., ge=0.0)
    font_size: float = Field(..., gt=0.0, description="Zipf log-normalized font size in pixels")
    font_family: str = Field(default="Inter", description="Must match a registered font name")
