"""Tests for the SSRF URL validator."""

from __future__ import annotations

import pytest

from app.utils.url_validator import URLValidationError, validate_url


class TestValidateURL:
    def test_valid_https_passes(self):
        # Should not raise
        validate_url("https://example.com/page")

    def test_valid_http_passes(self):
        validate_url("http://example.com/page")

    def test_localhost_blocked(self):
        with pytest.raises(URLValidationError, match="not permitted"):
            validate_url("http://localhost/admin")

    def test_file_scheme_blocked(self):
        with pytest.raises(URLValidationError, match="scheme"):
            validate_url("file:///etc/passwd")

    def test_ftp_scheme_blocked(self):
        with pytest.raises(URLValidationError, match="scheme"):
            validate_url("ftp://example.com/data")

    def test_loopback_ip_blocked(self):
        with pytest.raises(URLValidationError):
            validate_url("http://127.0.0.1/secret")

    def test_ipv6_loopback_blocked(self):
        with pytest.raises(URLValidationError):
            validate_url("http://[::1]/secret")

    def test_missing_hostname_blocked(self):
        with pytest.raises(URLValidationError, match="hostname"):
            validate_url("https:///path")

    def test_zero_ip_blocked(self):
        with pytest.raises(URLValidationError):
            validate_url("http://0.0.0.0/")
