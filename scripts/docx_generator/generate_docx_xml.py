#!/usr/bin/env python3
"""
Generate DOCX resume by rendering Jinja2 XML template.

This approach preserves 100% of the formatting from the template because
it works directly with the underlying OOXML structure.

Usage:
    python scripts/docx_generator/generate_docx_xml.py \
        --input content.json \
        --output resume.docx \
        --template resumes/reference/template.docx
"""

import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import Environment, FileSystemLoader, select_autoescape

AUTHOR = 'Alex Johnson'


def xml_escape(text: str) -> str:
    """Escape text for XML content."""
    if not isinstance(text, str):
        text = str(text)
    # Escape XML special characters
    text = escape(text, quote=False)
    # Also escape any remaining problematic characters
    return text


def parse_runs(text: str) -> list[dict]:
    """
    Parse a bullet string with **bold** markers into a list of run dicts.

    Example:
        "Deploy **Terraform** and **Ansible** pipelines"
        -> [{"text": "Deploy ", "bold": False},
            {"text": "Terraform", "bold": True},
            {"text": " and ", "bold": False},
            {"text": "Ansible", "bold": True},
            {"text": " pipelines", "bold": False}]

    Text without any ** markers returns a single non-bold run.
    """
    import re
    runs = []
    for i, part in enumerate(re.split(r'\*\*(.+?)\*\*', text)):
        if part:
            runs.append({'text': part, 'bold': bool(i % 2)})
    return runs if runs else [{'text': text, 'bold': False}]


def create_jinja_env(templates_dir: Path) -> Environment:
    """Create Jinja2 environment with XML-safe settings."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(['xml', 'j2']),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Add custom filters
    env.filters['xml_escape'] = xml_escape
    env.filters['parse_runs'] = parse_runs
    return env


def render_document_xml(env: Environment, content: dict) -> str:
    """Render the document.xml template with content."""
    template = env.get_template('document.xml.j2')
    return template.render(**content)


def build_clean_core_xml(author: str = AUTHOR) -> str:
    """Build a sanitized docProps/core.xml so template metadata (creator,
    lastPrinted, revision count) doesn't leak into the output."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    author_esc = xml_escape(author)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:creator>{author_esc}</dc:creator>'
        f'<cp:lastModifiedBy>{author_esc}</cp:lastModifiedBy>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        '<cp:revision>1</cp:revision>'
        '<dc:language>en-US</dc:language>'
        '</cp:coreProperties>'
    )


def create_docx(template_docx: Path, document_xml: str, output_path: Path):
    """
    Create a new DOCX by copying template and replacing document.xml.

    This preserves all other files (styles.xml, numbering.xml, etc.)
    while only replacing the content and sanitizing core metadata.
    """
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Extract template DOCX
        with zipfile.ZipFile(template_docx, 'r') as zf:
            zf.extractall(tmpdir)

        # Replace document.xml with rendered content
        doc_xml_path = tmpdir / 'word' / 'document.xml'
        doc_xml_path.write_text(document_xml, encoding='utf-8')

        # Sanitize core properties so template author/dates don't leak
        core_xml_path = tmpdir / 'docProps' / 'core.xml'
        core_xml_path.parent.mkdir(parents=True, exist_ok=True)
        core_xml_path.write_text(build_clean_core_xml(), encoding='utf-8')

        # Repackage as DOCX
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in tmpdir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir)
                    zf.write(file_path, arcname)

    print(f"Created: {output_path}")


def transform_content(content: dict) -> dict:
    """
    Transform the existing JSON schema to the template's expected format.

    Input schema (from tailor-resume workflow):
    {
        "name": "Alex Johnson",
        "contact": ["line1", "line2"],
        "sections": [
            {"title": "EXPERIENCE", "type": "experience", "entries": [...]},
            ...
        ]
    }

    Output schema (for Jinja2 template):
    {
        "name": "Alex Johnson",
        "contact": ["line1", "line2"],
        "experience": [...],  # All roles, entries with empty bullets render header-only
        "projects": [...],
        "technical_expertise": [...],
        "certifications": [...],
        "education": [...]
    }
    """
    result = {
        'name': content.get('name', ''),
        'contact': content.get('contact', []),
        'experience': [],
        'projects': [],
        'technical_expertise': [],
        'certifications': [],
        'education': [],
    }

    for section in content.get('sections', []):
        section_type = section.get('type', '')
        title = section.get('title', '').upper()

        if section_type == 'experience':
            result['experience'] = section.get('entries', [])
        elif section_type == 'projects':
            result['projects'] = section.get('entries', [])
        elif section_type == 'table':
            rows = section.get('rows', [])
            if 'SKILLS' in title:
                # Transform table rows to category/technologies format
                result['technical_expertise'] = [
                    {'category': row[0], 'technologies': row[1]}
                    for row in rows if len(row) >= 2
                ]
            elif 'CERTIFICATION' in title:
                # Transform table rows to abbrev/name/date format
                result['certifications'] = [
                    {'abbrev': row[0], 'name': row[1], 'date': row[2] if len(row) > 2 else ''}
                    for row in rows if len(row) >= 2
                ]
        elif section_type == 'education':
            result['education'] = section.get('entries', [])

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Generate DOCX resume from Jinja2 XML template'
    )
    parser.add_argument('--input', required=True, help='Path to JSON content file')
    parser.add_argument('--output', required=True, help='Output DOCX path')
    parser.add_argument('--template', required=True, help='Template DOCX path')
    parser.add_argument(
        '--templates-dir',
        default=None,
        help='Jinja2 templates directory (default: scripts/xml_template_poc/templates)'
    )

    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent
    templates_dir = Path(args.templates_dir) if args.templates_dir else script_dir / 'templates'

    # Load content
    with open(args.input) as f:
        content = json.load(f)

    # Transform content to template format
    template_content = transform_content(content)

    # Create Jinja2 environment and render
    env = create_jinja_env(templates_dir)
    document_xml = render_document_xml(env, template_content)

    # Create DOCX
    create_docx(
        Path(args.template),
        document_xml,
        Path(args.output)
    )


if __name__ == '__main__':
    main()
