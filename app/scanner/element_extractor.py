"""Element extractor – transforms a BeautifulSoup tree into structured PageElements.

Extraction is intentionally conservative: we capture what is useful for QA
without storing raw HTML blobs that would waste AI tokens.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from app.models.schemas import FormField, FormInfo, LinkInfo, PageElements


def extract_elements(soup: BeautifulSoup, base_url: str) -> PageElements:
    """Walk the parsed HTML tree and return a structured PageElements object."""
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    # ------------------------------------------------------------------
    # Page-level metadata
    # ------------------------------------------------------------------
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    meta_desc_tag = soup.find("meta", attrs={"name": lambda n: n and n.lower() == "description"})
    meta_description = (
        meta_desc_tag.get("content", "").strip()
        if isinstance(meta_desc_tag, Tag)
        else None
    )

    meta_kw_tag = soup.find("meta", attrs={"name": lambda n: n and n.lower() == "keywords"})
    meta_keywords = (
        meta_kw_tag.get("content", "").strip()
        if isinstance(meta_kw_tag, Tag)
        else None
    )

    viewport_tag = soup.find("meta", attrs={"name": lambda n: n and n.lower() == "viewport"})
    has_viewport_meta = viewport_tag is not None

    # ------------------------------------------------------------------
    # Forms
    # ------------------------------------------------------------------
    forms: list[FormInfo] = []
    standalone_inputs: list[FormField] = []

    for form_tag in soup.find_all("form"):
        action = form_tag.get("action") or None
        method = (form_tag.get("method") or "get").lower()
        fields: list[FormField] = []

        for inp in form_tag.find_all(["input", "select", "textarea"]):
            if not isinstance(inp, Tag):
                continue
            tag_name = inp.name or "input"
            input_type = inp.get("type", "text") if tag_name == "input" else tag_name
            if input_type in ("submit", "button", "reset", "hidden", "image"):
                continue
            fields.append(
                FormField(
                    name=inp.get("name") or inp.get("id") or None,
                    input_type=str(input_type),
                    required=inp.has_attr("required"),
                    placeholder=inp.get("placeholder") or None,
                )
            )

        forms.append(FormInfo(action=action, method=method, fields=fields))

    # Top-level inputs (not inside a form)
    for inp in soup.find_all(["input", "select", "textarea"]):
        if not isinstance(inp, Tag):
            continue
        if inp.find_parent("form"):
            continue
        tag_name = inp.name or "input"
        input_type = inp.get("type", "text") if tag_name == "input" else tag_name
        if input_type in ("submit", "button", "reset", "hidden", "image"):
            continue
        standalone_inputs.append(
            FormField(
                name=inp.get("name") or inp.get("id") or None,
                input_type=str(input_type),
                required=inp.has_attr("required"),
                placeholder=inp.get("placeholder") or None,
            )
        )

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    buttons: list[str] = []
    for btn in soup.find_all("button"):
        text = btn.get_text(strip=True)
        buttons.append(text or "[no text]")
    for inp in soup.find_all("input", attrs={"type": lambda t: t in ("submit", "button")}):
        if isinstance(inp, Tag):
            buttons.append(inp.get("value", "[button]"))

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------
    links: list[LinkInfo] = []
    for a_tag in soup.find_all("a", href=True):
        if not isinstance(a_tag, Tag):
            continue
        href = str(a_tag["href"]).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute_href = urljoin(base_url, href)
        link_domain = urlparse(absolute_href).netloc
        is_external = bool(link_domain) and link_domain != base_domain
        links.append(
            LinkInfo(
                href=absolute_href,
                text=a_tag.get_text(strip=True) or None,
                is_external=is_external,
            )
        )

    # ------------------------------------------------------------------
    # Images without alt
    # ------------------------------------------------------------------
    images_without_alt: list[str] = []
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        alt = img.get("alt")
        if alt is None or str(alt).strip() == "":
            src = img.get("src", "[no src]")
            images_without_alt.append(str(src))

    # ------------------------------------------------------------------
    # Heading structure (for UX / SEO checks)
    # ------------------------------------------------------------------
    heading_structure: list[str] = []
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            text = h.get_text(strip=True)[:80]
            heading_structure.append(f"h{level}: {text}")

    return PageElements(
        url=base_url,
        title=title,
        meta_description=meta_description or None,
        meta_keywords=meta_keywords or None,
        forms=forms,
        inputs=standalone_inputs,
        buttons=buttons,
        links=links,
        images_without_alt=images_without_alt,
        heading_structure=heading_structure,
        has_viewport_meta=has_viewport_meta,
    )
