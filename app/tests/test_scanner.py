"""Unit tests for the HTML scanner / element extractor."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.scanner.element_extractor import extract_elements
from app.scanner.html_parser import parse_html


BASE_URL = "https://example.com"


def _parse(html: str) -> BeautifulSoup:
    return parse_html(html)


class TestParseHTML:
    def test_returns_soup(self):
        soup = _parse("<html><body><p>Hello</p></body></html>")
        assert soup.find("p").get_text() == "Hello"

    def test_empty_html(self):
        soup = _parse("")
        assert soup is not None


class TestExtractElements:
    def test_title_extracted(self):
        soup = _parse("<html><head><title>My Page</title></head><body></body></html>")
        elements = extract_elements(soup, BASE_URL)
        assert elements.title == "My Page"

    def test_meta_description_extracted(self):
        html = '<html><head><meta name="description" content="About us"></head><body></body></html>'
        elements = extract_elements(_parse(html), BASE_URL)
        assert elements.meta_description == "About us"

    def test_viewport_meta_detected(self):
        html = '<html><head><meta name="viewport" content="width=device-width"></head><body></body></html>'
        elements = extract_elements(_parse(html), BASE_URL)
        assert elements.has_viewport_meta is True

    def test_no_viewport_meta(self):
        elements = extract_elements(_parse("<html><body></body></html>"), BASE_URL)
        assert elements.has_viewport_meta is False

    def test_form_extracted(self):
        html = """
        <html><body>
          <form action="/submit" method="post">
            <input type="text" name="username" required />
            <input type="password" name="password" />
            <input type="submit" value="Login" />
          </form>
        </body></html>
        """
        elements = extract_elements(_parse(html), BASE_URL)
        assert len(elements.forms) == 1
        form = elements.forms[0]
        assert form.action == "/submit"
        assert form.method == "post"
        # submit input should be excluded
        assert len(form.fields) == 2
        assert any(f.name == "username" and f.required for f in form.fields)

    def test_links_extracted(self):
        html = """
        <html><body>
          <a href="/about">About</a>
          <a href="https://external.com/page">External</a>
          <a href="#">Anchor</a>
          <a href="javascript:void(0)">JS</a>
        </body></html>
        """
        elements = extract_elements(_parse(html), BASE_URL)
        # Anchor and javascript: links should be ignored
        assert len(elements.links) == 2
        external = [l for l in elements.links if l.is_external]
        assert len(external) == 1
        assert external[0].href == "https://external.com/page"

    def test_images_without_alt_detected(self):
        html = """
        <html><body>
          <img src="logo.png" alt="Company Logo" />
          <img src="banner.png" />
          <img src="icon.png" alt="" />
        </body></html>
        """
        elements = extract_elements(_parse(html), BASE_URL)
        assert len(elements.images_without_alt) == 2
        assert "banner.png" in elements.images_without_alt

    def test_buttons_extracted(self):
        html = """
        <html><body>
          <button>Click me</button>
          <input type="submit" value="Submit" />
        </body></html>
        """
        elements = extract_elements(_parse(html), BASE_URL)
        assert len(elements.buttons) == 2
        assert "Click me" in elements.buttons
        assert "Submit" in elements.buttons

    def test_heading_structure_extracted(self):
        html = """
        <html><body>
          <h1>Main Title</h1>
          <h2>Section</h2>
          <h3>Subsection</h3>
        </body></html>
        """
        elements = extract_elements(_parse(html), BASE_URL)
        assert any("h1:" in h for h in elements.heading_structure)
        assert any("h2:" in h for h in elements.heading_structure)
