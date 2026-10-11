import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1] / 'knowledge'


def normalize(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.findall(r'[a-z0-9]+', text))


class Metadata(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-z0-9-]+$', max_length=100)
    title: str = Field(min_length=1, max_length=200)
    category: Literal['company', 'departments', 'products', 'playbooks']
    status: Literal['reference', 'proposed']
    version: int = Field(ge=1)
    updated_at: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    tags: list[str]
    sources: list[str]
    classification: Literal['internal-reference']
    author: str


class Knowledge:
    def __init__(self, root=ROOT):
        self.root, self.documents = Path(root).resolve(), {}
        manifest = json.loads((self.root / 'manifest.json').read_text(encoding='utf-8'))
        for entry in manifest['documents']:
            path = (self.root / entry['path']).resolve()
            if not path.is_relative_to(self.root) or 'generated' in path.parts:
                raise ValueError('Invalid knowledge path')
            text = path.read_text(encoding='utf-8')
            _, header, body = text.split('---', 2)
            metadata = Metadata.model_validate_json(header.strip())
            if metadata.id != entry['id'] or metadata.id in self.documents:
                raise ValueError('Duplicate/mismatched document ID')
            sections = []
            for section in re.split(r'(?m)^## ', body)[1:]:
                heading, _, content = section.partition('\n')
                sections.append({'id': normalize(heading).replace(' ', '-'), 'heading': heading.strip(), 'text': content.strip()})
            self.documents[metadata.id] = {'metadata': metadata.model_dump(), 'body': body.strip(), 'sections': sections}

    def get(self, document_id):
        if document_id not in self.documents:
            raise HTTPException(404, 'Knowledge document not found')
        return self.documents[document_id]

    def search(self, query, *, category=None, tag=None, limit=10, offset=0):
        q, ranked = normalize(query), []
        tokens = set(q.split())
        for document_id, document in self.documents.items():
            meta = document['metadata']
            if category and meta['category'] != category:
                continue
            if tag and not any(normalize(tag) in normalize(t) for t in meta['tags']):
                continue
            title, tags, body = normalize(meta['title']), normalize(' '.join(meta['tags'])), normalize(document['body'])
            score = (15 if q == normalize(document_id) else 0) + (8 if q and q in title else 0) + len(tokens & set(title.split())) * 3 + len(tokens & set(tags.split())) * 2 + min(4, len(tokens & set(body.split())))
            if not score and SequenceMatcher(None, q, title).ratio() >= .78:
                score = 2
            if score:
                sections = sorted(document['sections'], key=lambda s: -len(tokens & set(normalize(s['text'] + ' ' + s['heading']).split())))
                ranked.append({'document_id': document_id, 'title': meta['title'], 'status': meta['status'], 'score': min(score, 50), 'section': sections[0]['id'] if sections else None})
        ranked.sort(key=lambda r: (-r['score'], r['document_id']))
        return {'total': len(ranked), 'items': ranked[offset:offset + limit], 'offset': offset, 'limit': limit}
