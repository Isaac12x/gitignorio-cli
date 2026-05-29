from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gitignore_cli.mapping import OS_TEMPLATES
from gitignore_cli.templates import (
    CREATED_LINE,
    EDIT_LINE,
    END_LINE,
    SECTION_HEADER,
    TemplateStore,
)


@dataclass
class GitignoreFile:
    path: Path
    templates: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    preamble: str = ""
    managed: bool = False

    @classmethod
    def load(cls, path: Path, store: TemplateStore) -> GitignoreFile:
        if not path.exists():
            return cls(path=path)

        content = path.read_text(encoding="utf-8")
        parsed = cls(path=path)
        created = CREATED_LINE.search(content)
        edited = EDIT_LINE.search(content)
        parsed.managed = bool(created or edited)

        if created:
            parsed.templates = [part.strip().lower() for part in created.group(1).split(",") if part.strip()]
        elif edited:
            parsed.templates = [part.strip().lower() for part in edited.group(1).split(",") if part.strip()]

        end_match = END_LINE.search(content)
        body = content[: end_match.start()] if end_match else content

        if parsed.managed:
            first_section = SECTION_HEADER.search(body)
            parsed.preamble = body[: first_section.start()].strip() if first_section else body.strip()
            for title, section in store.extract_sections(body):
                template = store.title_to_template(title, candidates=parsed.templates)
                key = template or title.lower()
                parsed.sections[key] = section
        else:
            parsed.preamble = content.strip()

        return parsed

    def has_template(self, template: str) -> bool:
        template = template.lower()
        return template in self.templates or template in self.sections

    def template_present(self, store: TemplateStore, template: str, content: str | None = None) -> bool:
        template = template.lower()
        if self.has_template(template):
            return True
        if content is None:
            content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        if not content:
            return False
        title = store.section_title(template)
        return f"### {title} ###" in content

    def os_templates(self) -> list[str]:
        return [template for template in self.templates if template in OS_TEMPLATES]

    def language_templates(self) -> list[str]:
        return [template for template in self.templates if template not in OS_TEMPLATES]

    def render(self, store: TemplateStore, templates: list[str]) -> str:
        ordered = store.sort_templates(templates)
        if not ordered:
            return ""

        if not self.managed and self.preamble and not self.sections:
            joined = ",".join(ordered)
            appended = store.build_document(ordered)
            return f"{self.preamble.rstrip()}\n\n{appended.rstrip()}\n"

        joined = ",".join(ordered)
        header = (
            f"# Created by https://www.toptal.com/developers/gitignore/api/{joined}\n"
            f"# Edit at https://www.toptal.com/developers/gitignore?templates={joined}\n"
        )
        sections: list[str] = []
        for template in ordered:
            if template in self.sections:
                sections.append(self.sections[template].strip())
            else:
                sections.append(store.section_for_template(template).strip())

        body = "\n\n".join(section for section in sections if section)
        footer = f"# End of https://www.toptal.com/developers/gitignore/api/{joined}\n"
        return f"{header}\n{body.rstrip()}\n\n{footer}"

    def write(self, store: TemplateStore, templates: list[str]) -> None:
        content = self.render(store, templates)
        self.path.write_text(content, encoding="utf-8")

    def add_template(self, store: TemplateStore, template: str) -> bool:
        template = template.lower()
        if self.has_template(template):
            return False

        self.templates.append(template)
        self.sections[template] = store.section_for_template(template)
        self.managed = True
        return True

    def append_templates(self, store: TemplateStore, templates: list[str]) -> list[str]:
        """Append template sections without rewriting existing file content."""
        content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        added: list[str] = []

        for template in store.sort_templates(templates):
            if self.template_present(store, template, content):
                continue
            section = store.section_for_template(template).strip()
            if content and not content.endswith("\n"):
                content += "\n"
            if content.strip():
                content += "\n"
            content += section + "\n"
            added.append(template)
            if template not in self.templates:
                self.templates.append(template)
            self.sections[template] = section

        if added:
            self.path.write_text(content, encoding="utf-8")
        return added
