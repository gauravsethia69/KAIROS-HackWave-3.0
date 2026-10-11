"""Offline build step for the SORYU 24-page PDF. Runtime has no PDF dependencies.

Usage: python build_atlas_index.py "path/to/SORYU...pdf" [output.json]
Requires PyMuPDF only for this one-time generation: pip install pymupdf
"""
import hashlib
import json
import re
import sys
from pathlib import Path


def build(pdf_path: Path, output: Path):
    import fitz
    pdf_path = Path(pdf_path)
    doc = fitz.open(pdf_path)
    if len(doc) != 24:
        raise ValueError(f'Expected the 24-page SORYU Atlas; got {len(doc)} pages')
    chunks = []
    for i, page in enumerate(doc):
        lines = []
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                spans = line['spans']
                value = ''.join(s['text'] for s in spans).strip()
                if not value:
                    continue
                y = line['bbox'][1]
                if y < 105 or y > 490:  # excludes header, example prompts, graph hints and footer
                    continue
                size = max(s['size'] for s in spans)
                lines.append((y, round(size, 1), value))
        lines.sort(key=lambda t: t[0])
        title_lines = [v for _, size, v in lines if size >= 17]
        source_lines = [v for _, size, v in lines if v.startswith('Source ID:')]
        if len(title_lines) != 1 or len(source_lines) != 1:
            raise ValueError(f'Unexpected metadata layout on page {i + 1}')
        match = re.fullmatch(r'Source ID:\s*([a-z0-9-]+)\s*•\s*Status:\s*(reference|proposed)\s*•\s*Updated:\s*(\d{4}-\d\d-\d\d)', source_lines[0])
        if not match:
            raise ValueError(f'Unexpected source line on page {i + 1}: {source_lines[0]}')
        source_id, status, updated_at = match.groups()
        category = ('company' if i < 5 else 'departments' if i < 12 else 'products' if i < 16 else 'playbooks')
        heading = ''
        body_parts = []
        sections = []
        def finish_section():
            nonlocal body_parts
            if heading and body_parts:
                text = re.sub(r'\s+', ' ', ' '.join(body_parts)).strip()
                if text:
                    sections.append((heading, text))
            body_parts = []
        for _, size, value in lines:
            if value in title_lines or value.startswith('Source ID:'):
                continue
            if size >= 9.4 and size < 13 and not value.startswith('KNOWLEDGE'):
                finish_section()
                heading = value
            elif size >= 8.7 and size < 9.4 and heading:
                body_parts.append(value)
        finish_section()
        if len(sections) < 3:
            raise ValueError(f'Expected multiple meaningful sections on page {i + 1}; got {len(sections)}')
        for idx, (section, content) in enumerate(sections, 1):
            chunks.append({
                'id': f'atlas-p{i + 1:02d}-s{idx:02d}',
                'page': i + 1,
                'source_id': source_id,
                'category': category,
                'status': status,
                'updated_at': updated_at,
                'title': title_lines[0],
                'section': section,
                'text': content,
            })
    if len(set(c['source_id'] for c in chunks)) != 24:
        raise ValueError('Expected 24 unique authored source IDs')
    payload = {
        'schema': 'kairos-atlas-index-v1',
        'source_name': 'SORYU_SYSTEMS_24_Page_Knowledge_Atlas.pdf',
        'source_sha256': hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        'total_pages': len(doc),
        'chunk_count': len(chunks),
        'chunks': chunks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return len(chunks)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        raise SystemExit('Usage: python build_atlas_index.py "atlas.pdf" [output.json]')
    output = Path(sys.argv[2]) if len(sys.argv) == 3 else Path(__file__).resolve().parent.parent / 'backend/knowledge/atlas_index.json' if Path(__file__).resolve().parent.name == 'scripts' else Path(__file__).resolve().parent / 'backend/knowledge/atlas_index.json'
    count = build(Path(sys.argv[1]), output)
    print(f'Indexed 24 PDF pages into {count} source-labeled sections: {output}')
