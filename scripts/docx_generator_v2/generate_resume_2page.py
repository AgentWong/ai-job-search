#!/usr/bin/env python3
"""
Generate 2-page DOCX resume by rendering Jinja2 XML template.

This is the v2 generator that supports:
- Summary section
- Skills above Experience
- All roles with bullets (no prior_experience distinction)

Usage:
    python scripts/docx_generator_v2/generate_resume_2page.py \
        --input content.json \
        --output resume.docx \
        --template resumes/reference/template_2page.docx
"""

import argparse
import json
import zipfile
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import Environment, FileSystemLoader, select_autoescape


def xml_escape(text: str) -> str:
    """Escape text for XML content."""
    if not isinstance(text, str):
        text = str(text)
    return escape(text, quote=False)


def create_jinja_env(templates_dir: Path) -> Environment:
    """Create Jinja2 environment with XML-safe settings."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(['xml', 'j2']),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters['xml_escape'] = xml_escape
    return env


def render_document_xml(env: Environment, content: dict) -> str:
    """Render the 2-page document.xml template with content."""
    template = env.get_template('document_2page.xml.j2')
    return template.render(**content)


def create_docx(template_docx: Path, document_xml: str, output_path: Path):
    """
    Create a new DOCX by copying template and replacing document.xml.

    This preserves all other files (styles.xml, numbering.xml, etc.)
    while only replacing the content.
    """
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        with zipfile.ZipFile(template_docx, 'r') as zf:
            zf.extractall(tmpdir)

        doc_xml_path = tmpdir / 'word' / 'document.xml'
        doc_xml_path.write_text(document_xml, encoding='utf-8')

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in tmpdir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir)
                    zf.write(file_path, arcname)

    print(f"Created: {output_path}")


def transform_content(content: dict) -> dict:
    """
    Transform the JSON schema to the template's expected format.

    2-page resume schema changes from v1:
    - Add 'summary' field extraction
    - Remove prior_experience distinction (all experience entries have bullets)
    - Section order handled by template (Summary -> Skills -> Experience -> Projects -> Certs -> Education)

    Input schema:
    {
        "name": "Alex Johnson",
        "contact": ["line1", "line2"],
        "sections": [
            {"title": "SUMMARY", "type": "summary", "content": "..."},
            {"title": "SKILLS", "type": "table", "rows": [...]},
            {"title": "EXPERIENCE", "type": "experience", "entries": [...]},
            ...
        ]
    }

    Output schema (for Jinja2 template):
    {
        "name": "Alex Johnson",
        "contact": ["line1", "line2"],
        "summary": "...",
        "experience": [...],
        "projects": [...],
        "technical_expertise": [...],
        "certifications": [...],
        "education": [...]
    }
    """
    result = {
        'name': content.get('name', ''),
        'contact': content.get('contact', []),
        'summary': '',
        'experience': [],
        'projects': [],
        'technical_expertise': [],
        'certifications': [],
        'education': [],
    }

    for section in content.get('sections', []):
        section_type = section.get('type', '')
        title = section.get('title', '').upper()

        if section_type == 'summary':
            result['summary'] = section.get('content', '')
        elif section_type == 'experience':
            # All entries have bullets - no prior_experience distinction
            result['experience'] = section.get('entries', [])
        elif section_type == 'projects':
            result['projects'] = section.get('entries', [])
        elif section_type == 'table':
            rows = section.get('rows', [])
            if 'SKILLS' in title:
                result['technical_expertise'] = [
                    {'category': row[0], 'technologies': row[1]}
                    for row in rows if len(row) >= 2
                ]
            elif 'CERTIFICATION' in title:
                result['certifications'] = [
                    {'abbrev': row[0], 'name': row[1], 'date': row[2] if len(row) > 2 else ''}
                    for row in rows if len(row) >= 2
                ]
        elif section_type == 'education':
            result['education'] = section.get('entries', [])

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Generate 2-page DOCX resume from Jinja2 XML template'
    )
    parser.add_argument('--input', required=True, help='Path to JSON content file')
    parser.add_argument('--output', required=True, help='Output DOCX path')
    parser.add_argument('--template', required=True, help='Template DOCX path')
    parser.add_argument(
        '--templates-dir',
        default=None,
        help='Jinja2 templates directory (default: scripts/docx_generator_v2/templates)'
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    templates_dir = Path(args.templates_dir) if args.templates_dir else script_dir / 'templates'

    with open(args.input) as f:
        content = json.load(f)

    template_content = transform_content(content)

    env = create_jinja_env(templates_dir)
    document_xml = render_document_xml(env, template_content)

    create_docx(
        Path(args.template),
        document_xml,
        Path(args.output)
    )


if __name__ == '__main__':
    main()
