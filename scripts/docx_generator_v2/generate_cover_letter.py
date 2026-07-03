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


def render_document_xml(env: Environment, content: dict, template_name: str = 'cover_letter.xml.j2') -> str:
    """Render the cover letter template with content."""
    template = env.get_template(template_name)
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

        with zipfile.ZipFile(template_docx, 'r') as zf:
            zf.extractall(tmpdir)

        doc_xml_path = tmpdir / 'word' / 'document.xml'
        doc_xml_path.write_text(document_xml, encoding='utf-8')

        core_xml_path = tmpdir / 'docProps' / 'core.xml'
        core_xml_path.parent.mkdir(parents=True, exist_ok=True)
        core_xml_path.write_text(build_clean_core_xml(), encoding='utf-8')

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in tmpdir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir)
                    zf.write(file_path, arcname)

    print(f"Created: {output_path}")


def transform_content(content: dict) -> dict:
    """
    Transform JSON to template format for cover letter.

    Supports two formats:

    Point-by-point format (cover_letter.xml.j2):
    {
        "recipient": "Dear Recruiting Team:",
        "opening": "Opening paragraph...",
        "requirements": [
            {"requirement": "5+ years AWS experience", "bullets": ["Bullet 1...", "Bullet 2..."]}
        ],
        "closing": "Closing paragraph...",
        "signature": {"name": "...", "phone": "...", "email": "...", "linkedin": "..."}
    }

    Pitch format (cover_letter_pitch.xml.j2):
    {
        "recipient": "Dear Recruiting Team:",
        "paragraphs": ["Hook...", "Proof point...", "Close..."],
        "signature": {"name": "...", "phone": "...", "email": "...", "linkedin": "..."}
    }

    Output: Direct passthrough with defaults for missing fields
    """
    default_signature = {
        'name': 'Alex Johnson',
        'phone': '(555) 867-5309',
        'email': 'alex.johnson@example.com',
        'linkedin': 'https://linkedin.com/in/alexjohnson-devops'
    }

    # Pitch format: has "paragraphs" key
    if 'paragraphs' in content:
        return {
            'recipient': content.get('recipient', 'Dear Recruiting Team:'),
            'paragraphs': content.get('paragraphs', []),
            'signature': content.get('signature', default_signature)
        }

    # Point-by-point format: has "requirements" key
    return {
        'recipient': content.get('recipient', 'Dear Recruiting Team:'),
        'opening': content.get('opening', ''),
        'requirements': content.get('requirements', []),
        'closing': content.get('closing', ''),
        'signature': content.get('signature', default_signature)
    }


def main():
    parser = argparse.ArgumentParser(
        description='Generate DOCX cover letter from Jinja2 XML template'
    )
    parser.add_argument('--input', required=True, help='Path to JSON content file')
    parser.add_argument('--output', required=True, help='Output DOCX path')
    parser.add_argument('--template', required=True, help='Template DOCX path')
    parser.add_argument(
        '--template-name',
        default='cover_letter.xml.j2',
        help='Jinja2 template name (default: cover_letter.xml.j2)'
    )
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
    document_xml = render_document_xml(env, template_content, args.template_name)

    create_docx(
        Path(args.template),
        document_xml,
        Path(args.output)
    )


if __name__ == '__main__':
    main()
