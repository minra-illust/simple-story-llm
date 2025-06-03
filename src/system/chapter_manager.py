from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import json
import os
import threading
from .chapter import Chapter, Part
from .world_loader import WorldLoader


class ChapterManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.chapters: Dict[str, Chapter] = {}
            self.current_card = None
            self.default_values = {}
            self.runtime_path = None
            self.initialized = True
            self._change_callbacks = []
            self._save_timer = None
            self._pending_save = False
    
    def add_change_callback(self, callback):
        """Add a callback to be called when chapters change"""
        self._change_callbacks.append(callback)
    
    def _notify_changes(self):
        """Notify all callbacks of changes"""
        for callback in self._change_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Error in change callback: {e}")
    
    def set_current_card(self, card_name: str):
        """Set the current card and load default values"""
        self.current_card = card_name
        self.runtime_path = Path(f"runtime_saves/{card_name}")
        self.runtime_path.mkdir(parents=True, exist_ok=True)
        
        # Load default values from card
        card_path = Path(f"cards/{card_name}")
        if card_path.exists():
            loader = WorldLoader(card_path)
            world_data = loader.load_all()
            self.default_values = {
                'opening_summary': world_data.get('story_initial_context', ''),
                'places': world_data.get('places', ''),
                'facts': world_data.get('facts', ''),
                'vocabulary_guidance': world_data.get('vocabulary_guidance', '')
            }
        
        # Load existing chapters
        self.load_from_runtime()
    
    def create_chapter(self) -> Chapter:
        """Create a new chapter with default values"""
        chapter_num = len(self.chapters) + 1
        chapter = Chapter(f"chapter_{chapter_num}")
        
        # Apply default values from card
        chapter.opening_summary = self.default_values.get('opening_summary', '')
        chapter.places = self.default_values.get('places', '')
        chapter.facts = self.default_values.get('facts', '')
        chapter.vocabulary_guidance = self.default_values.get('vocabulary_guidance', '')
        
        # Add an initial empty part
        chapter.add_part()
        
        self.chapters[chapter.id] = chapter
        self.save_to_runtime(immediate=True)  # Immediate save for new chapter
        self._notify_changes()
        return chapter
    
    def delete_chapter(self, chapter_id: str):
        """Delete a chapter"""
        if chapter_id in self.chapters:
            del self.chapters[chapter_id]
            self.save_to_runtime(immediate=True)  # Immediate save for deletion
            self._notify_changes()
    
    def get_chapter(self, chapter_id: str) -> Optional[Chapter]:
        """Get a specific chapter"""
        return self.chapters.get(chapter_id)
    
    def get_all_chapters(self) -> List[Chapter]:
        """Get all chapters in order"""
        return sorted(self.chapters.values(), key=lambda c: c.created_at)
    
    def update_chapter(self, chapter_id: str, **kwargs):
        """Update chapter properties"""
        chapter = self.get_chapter(chapter_id)
        if chapter:
            for key, value in kwargs.items():
                if hasattr(chapter, key):
                    setattr(chapter, key, value)
            chapter.modified_at = datetime.now().isoformat()
            self.save_to_runtime()
            self._notify_changes()
    
    def update_part(self, chapter_id: str, part_id: str, **kwargs):
        """Update part properties"""
        chapter = self.get_chapter(chapter_id)
        if chapter:
            part = next((p for p in chapter.parts if p.id == part_id), None)
            if part:
                for key, value in kwargs.items():
                    if hasattr(part, key):
                        setattr(part, key, value)
                chapter.modified_at = datetime.now().isoformat()
                self.save_to_runtime()
                self._notify_changes()
    
    def save_to_runtime(self, immediate=False):
        """Save all chapters to runtime_saves"""
        if not self.runtime_path:
            return
        
        if immediate:
            # Immediate save
            self._do_save()
        else:
            # Debounced save - mark as pending
            self._pending_save = True
            
            # Cancel existing timer
            if self._save_timer is not None:
                self._save_timer.cancel()
            
            # Schedule save after 1 second of no changes
            self._save_timer = threading.Timer(1.0, self._do_save)
            self._save_timer.start()
    
    def _do_save(self):
        """Actually perform the save"""
        if not self.runtime_path or not self._pending_save:
            return
        
        try:
            # Save chapter index
            index_file = self.runtime_path / "chapters.json"
            index_data = {
                'card_name': self.current_card,
                'chapters': [c.to_dict() for c in self.get_all_chapters()]
            }
            
            with open(index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
            
            self._pending_save = False
        except Exception as e:
            print(f"Error saving chapters: {e}")
    
    def load_from_runtime(self):
        """Load chapters from runtime_saves"""
        if not self.runtime_path:
            return
        
        index_file = self.runtime_path / "chapters.json"
        if index_file.exists():
            with open(index_file, 'r') as f:
                data = json.load(f)
            
            self.chapters = {}
            for chapter_data in data.get('chapters', []):
                chapter = Chapter.from_dict(chapter_data)
                self.chapters[chapter.id] = chapter
            
            self._notify_changes()
    
    def shutdown(self):
        """Clean shutdown, ensuring pending saves are completed"""
        if self._save_timer is not None:
            self._save_timer.cancel()
        
        # Do final save if needed
        if self._pending_save:
            self._do_save()