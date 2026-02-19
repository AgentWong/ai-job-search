#!/usr/bin/env bash
# Convert all .docx files in this directory to PDF using LibreOffice

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

docx_files=("$SCRIPT_DIR"/*.docx)

if [ ! -e "${docx_files[0]}" ]; then
    echo "No .docx files found in $SCRIPT_DIR"
    exit 0
fi

echo "Converting ${#docx_files[@]} .docx file(s) to PDF..."

libreoffice --headless --convert-to pdf --outdir "$SCRIPT_DIR" "${docx_files[@]}"

echo "Done."
