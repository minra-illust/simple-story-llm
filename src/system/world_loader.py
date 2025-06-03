from pathlib import Path
from typing import Dict, Any, List
import yaml


class WorldLoader:
    def __init__(self, card_path: Path):
        self.card_path = card_path
    
    def load_all(self) -> Dict[str, Any]:
        world_data = {
            'characters': self._load_characters(),
            'places': self._load_places(),
            'facts': self._load_facts(),
            'story_initial_context': self._load_story_initial_context(),
            'vocabulary_guidance': self._load_vocabulary_guidance(),
        }
        return world_data
    
    def _load_characters(self) -> Dict[str, Dict[str, Any]]:
        characters = {}
        char_dir = self.card_path / "characters"
        
        if char_dir.exists():
            for char_file in char_dir.glob("*.md"):
                char_name = char_file.stem
                with open(char_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                characters[char_name] = {
                    'name': char_name,
                    'content': content
                }
        
        return characters
    
    def _load_places(self) -> str:
        # Try places.md first
        places_file = self.card_path / "places.md"
        if places_file.exists():
            with open(places_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        # If places is a directory, concatenate all .md files in it
        places_dir = self.card_path / "places"
        if places_dir.exists() and places_dir.is_dir():
            places_content = []
            for place_file in sorted(places_dir.glob("*.md")):
                with open(place_file, 'r', encoding='utf-8') as f:
                    places_content.append(f"## {place_file.stem}\n\n{f.read()}\n")
            return "\n".join(places_content)
        
        return ""
    
    def _load_facts(self) -> str:
        facts_file = self.card_path / "facts.md"
        if facts_file.exists():
            with open(facts_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def _load_story_initial_context(self) -> str:
        prog_file = self.card_path / "story_initial_context.md"
        if prog_file.exists():
            with open(prog_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        return ""
    
    def _load_vocabulary_guidance(self) -> str:
        prog_file = self.card_path / "vocabulary_guidance.md"
        if prog_file.exists():
            with open(prog_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""