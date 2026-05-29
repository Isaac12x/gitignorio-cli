from __future__ import annotations

import re
from functools import lru_cache

import httpx

API_BASE = "https://www.toptal.com/developers/gitignore/api"
CANONICAL_URL = "https://www.toptal.com/developers/gitignore"

CREATED_LINE = re.compile(
    r"^# Created by https://www\.toptal\.com/developers/gitignore/api/([^\s]+)\s*$",
    re.MULTILINE,
)
EDIT_LINE = re.compile(
    r"^# Edit at https://www\.toptal\.com/developers/gitignore\?templates=([^\s]+)\s*$",
    re.MULTILINE,
)
SECTION_HEADER = re.compile(r"^### (.+?) ###\s*$", re.MULTILINE)
END_LINE = re.compile(
    r"^# End of https://www\.toptal\.com/developers/gitignore/api/[^\s]+\s*$",
    re.MULTILINE,
)


class TemplateStore:
    def __init__(self) -> None:
        self._available: set[str] | None = None
        self._order: dict[str, int] | None = None
        self._section_titles: dict[str, str] = {}

    @property
    def available(self) -> set[str]:
        if self._available is None:
            self.refresh()
        assert self._available is not None
        return self._available

    @property
    def order(self) -> dict[str, int]:
        if self._order is None:
            self.refresh()
        assert self._order is not None
        return self._order

    def refresh(self) -> None:
        with httpx.Client(timeout=30.0) as client:
            list_response = client.get(f"{API_BASE}/list", params={"format": "lines"})
            list_response.raise_for_status()
            self._available = {
                line.strip().lower()
                for line in list_response.text.splitlines()
                if line.strip()
            }

            order_response = client.get(f"{API_BASE}/order")
            order_response.raise_for_status()
            self._order = {key.lower(): value for key, value in order_response.json().items()}

    def fetch_templates(self, templates: list[str]) -> str:
        if not templates:
            return ""
        key = ",".join(sorted(set(templates)))
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{API_BASE}/{key}")
            response.raise_for_status()
            return response.text

    def section_title(self, template: str) -> str:
        template = template.lower()
        if template not in self._section_titles:
            content = self.fetch_templates([template])
            match = SECTION_HEADER.search(content)
            self._section_titles[template] = match.group(1) if match else template
        return self._section_titles[template]

    def sort_templates(self, templates: list[str]) -> list[str]:
        return sorted(set(templates), key=lambda name: (self.order.get(name, 9999), name))

    def build_document(self, templates: list[str]) -> str:
        ordered = self.sort_templates(templates)
        if not ordered:
            return ""
        joined = ",".join(ordered)
        body = self.fetch_templates(ordered)
        if CREATED_LINE.search(body):
            return body

        sections = self.extract_sections(body)
        content = "\n\n".join(section.strip() for _, section in sections if section.strip())
        return (
            f"# Created by {API_BASE}/{joined}\n"
            f"# Edit at {CANONICAL_URL}?templates={joined}\n\n"
            f"{content.rstrip()}\n\n"
            f"# End of {API_BASE}/{joined}\n"
        )

    def extract_sections(self, content: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        matches = list(SECTION_HEADER.finditer(content))
        for index, match in enumerate(matches):
            title = match.group(1)
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            section_text = content[start:end].strip()
            if END_LINE.search(section_text):
                section_text = END_LINE.split(section_text)[0].strip()
            sections.append((title, section_text))
        return sections

    def section_for_template(self, template: str) -> str:
        content = self.fetch_templates([template])
        sections = self.extract_sections(content)
        if sections:
            return sections[0][1]
        return content.strip()

    def title_to_template(self, title: str, candidates: list[str] | None = None) -> str | None:
        normalized_title = re.sub(r"[^a-z0-9+]", "", title.lower())
        search_set = [candidate.lower() for candidate in (candidates or [])]

        for template in search_set:
            if template not in self.available:
                continue
            if re.sub(r"[^a-z0-9+]", "", template) == normalized_title:
                return template
            section_title = re.sub(r"[^a-z0-9+]", "", self.section_title(template).lower())
            if section_title == normalized_title:
                return template
        return None


@lru_cache(maxsize=1)
def get_store() -> TemplateStore:
    store = TemplateStore()
    store.refresh()
    return store
