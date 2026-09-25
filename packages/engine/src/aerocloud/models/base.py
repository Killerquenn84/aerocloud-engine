"""Shared Pydantic base class for all AeroCloud models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AeroCloudBase(BaseModel):
    """Immutable, strict, extra-forbidding base for every domain model.

    - ``frozen=True`` — models are hashable and cannot be mutated after construction
    - ``extra="forbid"`` — unknown fields raise ValidationError (prevents silent drift)
    - ``strict=True`` — no implicit type coercion (``1`` is not a string even if field is str)

    Downstream models should inherit and add their own fields without repeating
    ``model_config`` unless they need to override something.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )
