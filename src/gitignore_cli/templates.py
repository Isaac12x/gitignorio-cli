from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files

API_BASE = "https://gitignore.org/api"
CANONICAL_URL = "https://gitignore.org"

_API_PAT = r"(?:https://(?:gitignore\.org|(?:www\.)?gitignore\.io|www\.toptal\.com/developers/gitignore)/api)"
_EDIT_PAT = r"(?:https://(?:gitignore\.org|(?:www\.)?gitignore\.io|www\.toptal\.com/developers/gitignore))"

CREATED_LINE = re.compile(
    rf"^# Created by {_API_PAT}/([^\s]+)\s*$",
    re.MULTILINE,
)
EDIT_LINE = re.compile(
    rf"^# Edit at {_EDIT_PAT}\?templates=([^\s]+)\s*$",
    re.MULTILINE,
)
SECTION_HEADER = re.compile(r"^### (.+?) ###\s*$", re.MULTILINE)
END_LINE = re.compile(
    rf"^# End of {_API_PAT}/[^\s]+\s*$",
    re.MULTILINE,
)

_DATA_ROOT = files("gitignore_cli") / "data"


class TemplateStore:
    def __init__(self) -> None:
        self._available: set[str] | None = None
        self._order: dict[str, int] | None = None
        self._section_titles: dict[str, str] = {}
        self._template_cache: dict[str, str] = {}

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
        list_text = (_DATA_ROOT / "list.txt").read_text(encoding="utf-8")
        self._available = {
            line.strip().lower()
            for line in list_text.splitlines()
            if line.strip()
        }

        order_text = (_DATA_ROOT / "order.json").read_text(encoding="utf-8")
        self._order = {key.lower(): value for key, value in json.loads(order_text).items()}

    def _load_template(self, template: str) -> str:
        template = template.lower()
        if template not in self._template_cache:
            path = _DATA_ROOT / "templates" / f"{template}.gitignore"
            self._template_cache[template] = path.read_text(encoding="utf-8")
        return self._template_cache[template]

    def _strip_template_wrapper(self, content: str) -> str:
        body = content
        if CREATED_LINE.search(body):
            body = CREATED_LINE.split(body, maxsplit=1)[-1]
        body = EDIT_LINE.sub("", body, count=1)
        if END_LINE.search(body):
            body = END_LINE.split(body)[0]
        return body.strip()

    def fetch_templates(self, templates: list[str]) -> str:
        if not templates:
            return ""
        ordered = self.sort_templates(list(set(templates)))
        if len(ordered) == 1:
            return self._load_template(ordered[0])

        parts: list[str] = []
        for template in ordered:
            content = self._load_template(template)
            sections = self.extract_sections(content)
            if sections:
                parts.append(sections[0][1].strip())
            else:
                parts.append(self._strip_template_wrapper(content))
        return "\n\n".join(part for part in parts if part)

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
        if not content:
            content = body.strip()
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
