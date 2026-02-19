#!/usr/bin/env python3
"""
Generate DOCX cover letter by rendering Jinja2 XML template.

Generates point-by-point cover letters matching job requirements to CV content.

Usage:
    python scripts/docx_generator_v2/generate_cover_letter.py \
        --input cover_letter_content.json \
        --output cover_letter.docx \
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
    """Render the cover letter template with content."""
    template = env.get_template('cover_letter.xml.j2')
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
    Transform JSON to template format for cover letter.

    Input schema:
    {
        "recipient": "Dear Recruiting Team:",
        "opening": "Opening paragraph...",
        "requirements": [
            {"requirement": "5+ years AWS experience", "bullets": ["Bullet 1...", "Bullet 2..."]}
        ],
        "closing": "Closing paragraph...",
        "signature": {"name": "...", "phone": "...", "email": "...", "linkedin": "..."}
    }

    Output: Direct passthrough with defaults for missing fields
    """
    return {
        'recipient': content.get('recipient', 'Dear Recruiting Team:'),
        'opening': content.get('opening', ''),
        'requirements': content.get('requirements', []),
        'closing': content.get('closing', ''),
        'signature': content.get('signature', {
            'name': 'Alex Johnson',
            'phone': '(555) 867-5309',
            'email': 'alex.johnson@example.com',
            'linkedin': 'https://linkedin.com/in/alexjohnson-devops'
        })
    }


def main():
    parser = argparse.ArgumentParser(
        description='Generate DOCX cover letter from Jinja2 XML template'
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
