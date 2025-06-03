from typing import Dict, Any, List
from datetime import datetime

from .llm_wrapper import LLM


class NarrationsProcessor:
    def __init__(self):
        self.llm = LLM(filename_prefix="_llm_call_narrations_processor_rq")
    
    def _extract_narration_log(self, narrative: str) -> str:
        """Extracts the content of the NARRATION_LOG section from the narrative string."""
        start_tag = "<NARRATION_LOG>"
        end_tag = "</NARRATION_LOG>"
        
        start_idx = narrative.find(start_tag)
        if start_idx == -1:
            return None
        start_idx += len(start_tag)
        
        end_idx = narrative.find(end_tag, start_idx)
        if end_idx == -1:
            return None
        
        return narrative[start_idx:end_idx].strip()
    
    def process(
        self,
        narrative: str,
        world_data: Dict[str, Any],
        user_input: str,
        log_history: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        
        # Extract key information from narrative
        extracted_info = self._extract_key_information(narrative, user_input)
        
        # Extract the NARRATION_LOG section
        narration_log = self._extract_narration_log(narrative)
        
        # Build processed log entry
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_input': user_input,
            'summary': extracted_info.get('summary', ''),
            'key_facts': extracted_info.get('key_facts', []),
            'character_states': extracted_info.get('character_states', {}),
            'location': extracted_info.get('location', ''),
            'narrative_snippet': narrative[:200] + '...' if len(narrative) > 200 else narrative,
            'narration_log': narration_log if narration_log else narrative  # Store full NARRATION_LOG or fallback to full narrative
        }
        
        return log_entry
    
    def _extract_key_information(
        self,
        narrative: str,
        user_input: str
    ) -> Dict[str, Any]:
        
        prompt = f"""Extract key information from this narrative for future reference.

User Input: {user_input}

Narrative:
{narrative}

Extract:
1. A one-sentence summary of what happened
2. Key facts that should be remembered (list of strings). Focus on:
   - Character actions (what they did)
   - Character dialogue (extract verbatim, exactly as written including quotation marks)
   - Important objects or events only if they significantly impact the story
   - Information about mood and intentions of characters
   - DO NOT paraphrase dialogue - copy it exactly as it appears in the narrative
3. Current character emotional states or changes (dict of character_name: state)
4. Current location if mentioned

Rule for extraction:
1. Key facts must be summarized and combined if possible
2. Dialogues should be extracted verbatim

Return as JSON with keys: summary, key_facts, character_states, location"""
        
        try:
            response = self.llm.chat_sync(prompt, model_index=1)
            
            # Parse JSON response
            import json
            
            # Try to extract JSON from the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
            else:
                # Fallback if no valid JSON
                return {
                    'summary': 'Narration occurred',
                    'key_facts': [],
                    'character_states': {},
                    'location': ''
                }
                
        except Exception as e:
            print(f"Error extracting information: {e}")
            return {
                'summary': user_input,
                'key_facts': [],
                'character_states': {},
                'location': ''
            }
    
    def get_context_for_part(self, log_history: List[Dict[str, Any]], part_number: int = 1) -> List[Dict[str, Any]]:
        # Return log entries based on part number
        
        if not log_history:
            return []
        
        # For any part, return all available logs
        # SimpleAida will handle the filtering and key fact extraction
        return log_history