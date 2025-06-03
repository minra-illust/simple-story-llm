from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import json


class Part:
    def __init__(self, number: int, chapter_id: str):
        self.id = str(uuid.uuid4())
        self.number = number
        self.chapter_id = chapter_id
        self.user_input = ""
        self.narration_log = ""
        self.processed_log = {}
        self.is_generated = False
        self.generation_timestamp = None
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'number': self.number,
            'chapter_id': self.chapter_id,
            'user_input': self.user_input,
            'narration_log': self.narration_log,
            'processed_log': self.processed_log,
            'is_generated': self.is_generated,
            'generation_timestamp': self.generation_timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Part':
        part = cls(data['number'], data['chapter_id'])
        part.id = data['id']
        part.user_input = data.get('user_input', '')
        part.narration_log = data.get('narration_log', '')
        part.processed_log = data.get('processed_log', {})
        part.is_generated = data.get('is_generated', False)
        part.generation_timestamp = data.get('generation_timestamp')
        return part


class Chapter:
    def __init__(self, name: str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.opening_summary = ""
        self.places = ""
        self.facts = ""
        self.vocabulary_guidance = ""
        self.parts: List[Part] = []
        self.is_generated = False
        self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
        
    def add_part(self) -> Part:
        part_number = len(self.parts) + 1
        part = Part(part_number, self.id)
        self.parts.append(part)
        self.modified_at = datetime.now().isoformat()
        return part
    
    def remove_part(self, part_id: str):
        self.parts = [p for p in self.parts if p.id != part_id]
        # Renumber remaining parts
        for i, part in enumerate(self.parts):
            part.number = i + 1
        self.modified_at = datetime.now().isoformat()
    
    def get_non_empty_parts(self) -> List[Part]:
        return [p for p in self.parts if p.user_input.strip()]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'opening_summary': self.opening_summary,
            'places': self.places,
            'facts': self.facts,
            'vocabulary_guidance': self.vocabulary_guidance,
            'parts': [p.to_dict() for p in self.parts],
            'is_generated': self.is_generated,
            'created_at': self.created_at,
            'modified_at': self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Chapter':
        chapter = cls(data['name'])
        chapter.id = data['id']
        chapter.opening_summary = data.get('opening_summary', '')
        chapter.places = data.get('places', '')
        chapter.facts = data.get('facts', '')
        chapter.vocabulary_guidance = data.get('vocabulary_guidance', '')
        chapter.parts = [Part.from_dict(p) for p in data.get('parts', [])]
        chapter.is_generated = data.get('is_generated', False)
        chapter.created_at = data.get('created_at', datetime.now().isoformat())
        chapter.modified_at = data.get('modified_at', datetime.now().isoformat())
        return chapter