from pathlib import Path
from typing import Dict, Any, List

from ..llm_wrapper import LLM


class SimpleAida:
    def __init__(self, card_path: Path):
        self.card_path = card_path
        self.card_name = card_path.name
        self.llm = LLM(filename_prefix="_llm_call_simple_aida_rq")
        self._load_prompts()
    
    def _load_prompts(self):
        # Load main AIDA prompt
        prompt_file = Path(__file__).parent / "simple_prompt.md"
        if prompt_file.exists():
            with open(prompt_file, 'r') as f:
                self.base_prompt = f.read()
        else:
            self.base_prompt = self._default_prompt()
        
    
    def _default_prompt(self) -> str:
        return """"""
    
    async def generate(
        self,
        world_data: Dict[str, Any],
        log_context: List[Dict[str, Any]],
        beats: List[Dict[str, str]],
        part_number: int = 1
    ) -> Dict[str, Any]:
        
        # Build the prompt with beats
        prompt = self._build_prompt(world_data, log_context, beats, part_number)
        
        # Generate narrative
        narrative = await self.llm.chat(prompt, system_prompt="You are an expert writer focused on plausible stories with rich ways to convey your story, in depth and in breath. When thinking, use 'Wait,' frequently to double check everything.")
        
        # Format beats for return value
        beats_summary = ' // '.join(beat['content'] for beat in beats)
        
        return {
            'narrative': narrative,
            'user_input': beats_summary,
            'beats': beats
        }
    
    def _build_prompt(
        self,
        world_data: Dict[str, Any],
        log_context: List[Dict[str, Any]],
        beats: List[Dict[str, str]],
        part_number: int = 1
    ) -> str:
        
        sections = [self.base_prompt, "\n"]
        
        # Add world context
        sections.append("# DATA FILES\n")
        
        # Characters
        if world_data.get('characters'):
            sections.append("## Characters\n")
            for char_name, char_data in world_data['characters'].items():
                sections.append(f"**{char_name}**:\n{char_data['content']}\n")
        
        # Places
        if world_data.get('places'):
            sections.append("\n## Places\n")
            sections.append(world_data['places'] + "\n")
        
        # Facts
        if world_data.get('facts'):
            sections.append("\n## World Facts\n")
            sections.append(world_data['facts'] + "\n")
        
        # Chapter context (if provided)
        if world_data.get('chapter_context'):
            sections.append("\n## Chapter Context\n")
            sections.append(world_data['chapter_context'])
        
        # Opening
        if world_data.get('story_initial_context'):
            sections.append("\n## Initial Context (before any narration item)\n")
            sections.append(world_data['story_initial_context'] + "\n")
        
        # Opening
        if world_data.get('vocabulary_guidance'):
            sections.append("\n## Vocabulary Guidance\n")
            sections.append(world_data['vocabulary_guidance'] + "\n")
        
        # Previous narrations
        if log_context:
            sections.append("\n## Past Narrative items\n")
            
            # Check if there are any key facts to show
            has_key_facts = any(
                log.get('summary') or log.get('key_facts') or log.get('location') or log.get('character_states')
                for log in log_context
            )
            
            if has_key_facts:
                # For ALL turns, show only key facts to prevent repetition
                sections.append("\n### Key Facts from Previous Turns\n")
                
                # Show key facts from all previous turns
                for i, log in enumerate(log_context):
                    part_num = i + 1
                    
                    # Only add part header if there's content to show
                    part_content = []
                    
                    if 'key_facts' in log and log['key_facts']:
                        part_content.append("Key Facts:\n")
                        for fact in log['key_facts']:
                            part_content.append(f"- {fact}\n")
                    
                    # Only add part section if there's meaningful content
                    if len(part_content) > 0:
                        sections.append(f"\n**Part {part_num}**\n")
                        sections.extend(part_content)
        
        # Add beats section
        sections.append("\n## Director Beats\n")
        sections.append("Expand the following story beats into a complete narrative:\n\n")
        
        for i, beat in enumerate(beats):
            beat_label = beat['type'].capitalize()
            sections.append(f"**{beat_label} Beat**: {beat['content']}\n")
        
        sections.append("\nRemember:\n")
        sections.append("- Start beats establish the scene and introduce elements\n")
        sections.append("- Middle beats develop action and build tension\n")
        sections.append("- Finish beats resolve or transition to the next scene\n")
        sections.append("- Complete beats (when there's only one) should encompass all three aspects\n")
        
        return "".join(sections)
