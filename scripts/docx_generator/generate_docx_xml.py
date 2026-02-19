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
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import Environment, FileSystemLoader, select_autoescape


def xml_escape(text: str) -> str:
    """Escape text for XML content."""
    if not isinstance(text, str):
        text = str(text)
    # Escape XML special characters
    text = escape(text, quote=False)
    # Also escape any remaining problematic characters
    return text


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
    return env


def render_document_xml(env: Environment, content: dict) -> str:
    """Render the document.xml template with content."""
    template = env.get_template('document.xml.j2')
    return template.render(**content)


def create_docx(template_docx: Path, document_xml: str, output_path: Path):
    """
    Create a new DOCX by copying template and replacing document.xml.

    This preserves all other files (styles.xml, numbering.xml, etc.)
    while only replacing the content.
    """
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Extract template DOCX
        with zipfile.ZipFile(template_docx, 'r') as zf:
            zf.extractall(tmpdir)

        # Replace document.xml with rendered content
        doc_xml_path = tmpdir / 'word' / 'document.xml'
        doc_xml_path.write_text(document_xml, encoding='utf-8')

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
        "experience": [...],
        "prior_experience": [...],  # Earlier roles with minimal info (no bullets)
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
        'prior_experience': [],
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
            result['prior_experience'] = section.get('prior_experience', [])
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
