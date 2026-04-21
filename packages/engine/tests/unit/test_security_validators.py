"""TDD tests for security validators (PROD-13, PROD-14, PROD-15).

All tests written BEFORE implementation (RED phase).
Tests verify:
- validate_hex_color: regex ^#[0-9a-fA-F]{3,8}$ per D-15
- validate_font_name: allow-list from assets/fonts/ directory
- validate_no_path_traversal: rejects ../, .., null bytes
- RenderRequest Pydantic integration for font_family, shape_b64, colors
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aerocloud.models.security import (
    validate_hex_color,
    validate_font_name,
    validate_no_path_traversal,
    get_allowed_fonts,
    HEX_COLOR_RE,
)


# ---------------------------------------------------------------------------
# validate_hex_color
# ---------------------------------------------------------------------------

class TestValidateHexColor:
    """Tests for color allow-list validator (PROD-15, D-15)."""

    # Valid colors
    def test_accepts_3_char_hex(self) -> None:
        """'#fff' is valid (3 hex chars)."""
        assert validate_hex_color("#fff") == "#fff"

    def test_accepts_6_char_hex(self) -> None:
        """'#ffffff' is valid (6 hex chars)."""
        assert validate_hex_color("#ffffff") == "#ffffff"

    def test_accepts_8_char_hex(self) -> None:
        """'#ffffffff' is valid (8 hex chars, with alpha)."""
        assert validate_hex_color("#ffffffff") == "#ffffffff"

    def test_accepts_uppercase_hex(self) -> None:
        """'#FF0000' is valid (uppercase)."""
        assert validate_hex_color("#FF0000") == "#FF0000"

    def test_accepts_mixed_case_hex(self) -> None:
        """'#aAbBcC' is valid (mixed case)."""
        assert validate_hex_color("#aAbBcC") == "#aAbBcC"

    def test_accepts_3_char_hex_digits(self) -> None:
        """'#123' is valid (3 hex digits)."""
        assert validate_hex_color("#123") == "#123"

    # Invalid colors
    def test_rejects_named_color(self) -> None:
        """'red' is rejected (not a hex string)."""
        with pytest.raises(ValueError):
            validate_hex_color("red")

    def test_rejects_rgb_function(self) -> None:
        """'rgb(0,0,0)' is rejected."""
        with pytest.raises(ValueError):
            validate_hex_color("rgb(0,0,0)")

    def test_rejects_invalid_hex_chars(self) -> None:
        """'#xyz' is rejected (non-hex characters)."""
        with pytest.raises(ValueError):
            validate_hex_color("#xyz")

    def test_rejects_empty_string(self) -> None:
        """Empty string is rejected."""
        with pytest.raises(ValueError):
            validate_hex_color("")

    def test_rejects_javascript_injection(self) -> None:
        """'javascript:alert(1)' is rejected (XSS attempt)."""
        with pytest.raises(ValueError):
            validate_hex_color("javascript:alert(1)")

    def test_rejects_missing_hash(self) -> None:
        """'ffffff' without leading # is rejected."""
        with pytest.raises(ValueError):
            validate_hex_color("ffffff")

    def test_rejects_too_short(self) -> None:
        """'#ab' (2 hex chars) is rejected (minimum is 3)."""
        with pytest.raises(ValueError):
            validate_hex_color("#ab")

    def test_rejects_too_long(self) -> None:
        """'#aabbccdd11' (9+ hex chars) is rejected (maximum is 8)."""
        with pytest.raises(ValueError):
            validate_hex_color("#aabbccdd11")

    def test_returns_original_string_on_success(self) -> None:
        """Validator returns the original string unmodified."""
        color = "#a1B2c3"
        assert validate_hex_color(color) is color or validate_hex_color(color) == color


class TestHexColorRegex:
    """Verify the regex constant matches D-15 specification exactly."""

    def test_regex_pattern_is_correct(self) -> None:
        """HEX_COLOR_RE pattern is exactly ^#[0-9a-fA-F]{3,8}$."""
        assert HEX_COLOR_RE.pattern == r"^#[0-9a-fA-F]{3,8}$"

    def test_fullmatch_3_chars(self) -> None:
        assert HEX_COLOR_RE.fullmatch("#abc") is not None

    def test_fullmatch_6_chars(self) -> None:
        assert HEX_COLOR_RE.fullmatch("#abcdef") is not None

    def test_no_match_named(self) -> None:
        assert HEX_COLOR_RE.fullmatch("red") is None


# ---------------------------------------------------------------------------
# get_allowed_fonts
# ---------------------------------------------------------------------------

class TestGetAllowedFonts:
    """Tests for font allow-list loader (PROD-14, D-16)."""

    def test_returns_frozenset(self) -> None:
        """get_allowed_fonts returns a frozenset."""
        fonts = get_allowed_fonts()
        assert isinstance(fonts, frozenset)

    def test_inter_is_in_allowed_fonts(self) -> None:
        """'Inter' is present (assets/fonts/Inter/ exists)."""
        fonts = get_allowed_fonts()
        assert "Inter" in fonts, f"Expected 'Inter' in allowed fonts, got: {fonts}"

    def test_is_non_empty(self) -> None:
        """Allowed fonts set is not empty."""
        fonts = get_allowed_fonts()
        assert len(fonts) > 0


# ---------------------------------------------------------------------------
# validate_font_name
# ---------------------------------------------------------------------------

class TestValidateFontName:
    """Tests for font name validator (PROD-14, D-16)."""

    def test_accepts_inter(self) -> None:
        """'Inter' is accepted (in assets/fonts/)."""
        result = validate_font_name("Inter")
        assert result == "Inter"

    def test_rejects_unlisted_font(self) -> None:
        """'EvilFont' is rejected when not in allowed set."""
        with pytest.raises(ValueError):
            validate_font_name("EvilFont")

    def test_rejects_empty_string(self) -> None:
        """Empty string is rejected."""
        with pytest.raises(ValueError):
            validate_font_name("")

    def test_custom_allowed_set_accepted(self) -> None:
        """Custom allowed set: 'TestFont' accepted when in provided set."""
        result = validate_font_name("TestFont", allowed=frozenset({"TestFont", "Other"}))
        assert result == "TestFont"

    def test_custom_allowed_set_rejected(self) -> None:
        """Custom allowed set: 'BadFont' rejected when not in provided set."""
        with pytest.raises(ValueError):
            validate_font_name("BadFont", allowed=frozenset({"TestFont"}))

    def test_returns_original_string_on_success(self) -> None:
        """Validator returns the original string unmodified."""
        name = "Inter"
        result = validate_font_name(name)
        assert result == name


# ---------------------------------------------------------------------------
# validate_no_path_traversal
# ---------------------------------------------------------------------------

class TestValidateNoPathTraversal:
    """Tests for path traversal prevention (PROD-13, D-17)."""

    # Rejections
    def test_rejects_unix_traversal(self) -> None:
        """'../' pattern is rejected."""
        with pytest.raises(ValueError):
            validate_no_path_traversal("../../etc/passwd")

    def test_rejects_windows_traversal(self) -> None:
        r"""'..\' pattern is rejected."""
        with pytest.raises(ValueError):
            validate_no_path_traversal(r"..\secret")

    def test_rejects_null_byte(self) -> None:
        """Null byte (\\x00) is rejected."""
        with pytest.raises(ValueError):
            validate_no_path_traversal("normal\x00evil")

    def test_rejects_embedded_traversal(self) -> None:
        """Path traversal embedded in base64-like string is rejected."""
        with pytest.raises(ValueError):
            validate_no_path_traversal("abc../def")

    def test_rejects_windows_traversal_in_middle(self) -> None:
        r"""Windows traversal embedded mid-string is rejected."""
        with pytest.raises(ValueError):
            validate_no_path_traversal(r"data..\..\secret")

    # Accepted values
    def test_accepts_normal_base64(self) -> None:
        """Normal base64 string is accepted."""
        b64 = "SGVsbG8gV29ybGQ="
        result = validate_no_path_traversal(b64)
        assert result == b64

    def test_accepts_empty_string(self) -> None:
        """Empty string is accepted (no traversal patterns)."""
        result = validate_no_path_traversal("")
        assert result == ""

    def test_accepts_plain_text(self) -> None:
        """Plain text without traversal patterns is accepted."""
        result = validate_no_path_traversal("hello world")
        assert result == "hello world"

    def test_returns_original_string_on_success(self) -> None:
        """Validator returns the original string unmodified."""
        value = "safe_value_123"
        result = validate_no_path_traversal(value)
        assert result == value


# ---------------------------------------------------------------------------
# RenderRequest integration
# ---------------------------------------------------------------------------

class TestRenderRequestIntegration:
    """Integration tests: validators wired into RenderRequest Pydantic model."""

    def test_render_request_rejects_invalid_font(self) -> None:
        """RenderRequest with font_family not in allow-list raises ValidationError."""
        with pytest.raises(ValidationError):
            from aerocloud.models.api import RenderRequest
            RenderRequest(
                text="hello",
                shape_b64="SGVsbG8=",
                font_family="EvilFont",
            )

    def test_render_request_rejects_path_traversal_in_shape_b64(self) -> None:
        """RenderRequest with shape_b64 containing '../' raises ValidationError."""
        with pytest.raises(ValidationError):
            from aerocloud.models.api import RenderRequest
            RenderRequest(
                text="hello",
                shape_b64="../../etc/passwd",
            )

    def test_render_request_accepts_valid_inter_font(self) -> None:
        """RenderRequest with font_family='Inter' is accepted."""
        from aerocloud.models.api import RenderRequest
        req = RenderRequest(
            text="hello",
            shape_b64="SGVsbG8=",
            font_family="Inter",
        )
        assert req.font_family == "Inter"

    def test_render_request_accepts_valid_colors(self) -> None:
        """RenderRequest with valid hex colors list is accepted."""
        from aerocloud.models.api import RenderRequest
        req = RenderRequest(
            text="hello",
            shape_b64="SGVsbG8=",
            colors=["#ff0000", "#00ff00", "#0000ff"],
        )
        assert req.colors == ["#ff0000", "#00ff00", "#0000ff"]

    def test_render_request_rejects_invalid_color(self) -> None:
        """RenderRequest with invalid color in colors list raises ValidationError."""
        with pytest.raises(ValidationError):
            from aerocloud.models.api import RenderRequest
            RenderRequest(
                text="hello",
                shape_b64="SGVsbG8=",
                colors=["red"],  # named color, not hex
            )

    def test_render_request_accepts_none_colors(self) -> None:
        """RenderRequest with colors=None is accepted (default)."""
        from aerocloud.models.api import RenderRequest
        req = RenderRequest(
            text="hello",
            shape_b64="SGVsbG8=",
        )
        assert req.colors is None
