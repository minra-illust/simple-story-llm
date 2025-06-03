"""Wrapper for the LLM functions to provide a class interface."""

import asyncio
from typing import List, Dict, Any
from .llm import llm_call


class LLM:
    """Wrapper class for LLM functionality."""
    
    def __init__(self, log_dir=None, filename_prefix="_last_llm_call"):
        self.current_model = 0  # Default model index
        self.log_dir = log_dir
        self.filename_prefix = filename_prefix
    
    async def chat(self, prompt: str, model_index: int = None, system_prompt: str = '') -> str:
        """
        Async wrapper for chat functionality.
        
        Args:
            prompt: The prompt to send to the LLM
            model_index: Optional specific model to use
            system_prompt: Optional system prompt to prepend to conversation
            
        Returns:
            The LLM's response as a string
        """
        if model_index is None:
            model_index = self.current_model
            
        # Convert single prompt to messages format
        messages = [{"role": "user", "content": prompt}]
        
        # Determine log files
        if self.log_dir:
            from pathlib import Path
            log_dir = Path(self.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_filename = str(log_dir / f'{self.filename_prefix}.log')
            result_log_filename = str(log_dir / f'{self.filename_prefix[:-2]}rs.log')
        else:
            log_filename = f'{self.filename_prefix}.log'
            result_log_filename = f'{self.filename_prefix[:-2]}rs.log'
        
        # Run the synchronous llm_call in a thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,  # Use default executor
            llm_call,
            messages,
            model_index,
            log_filename,
            result_log_filename,
            system_prompt
        )
        
        return (response or "").replace('\u2019', "'")
    
    def chat_sync(self, prompt: str, model_index: int = None, system_prompt: str = '') -> str:
        """
        Synchronous wrapper for chat functionality.
        
        Args:
            prompt: The prompt to send to the LLM
            model_index: Optional specific model to use
            system_prompt: Optional system prompt to prepend to conversation
            
        Returns:
            The LLM's response as a string
        """
        if model_index is None:
            model_index = self.current_model
            
        # Convert single prompt to messages format
        messages = [{"role": "user", "content": prompt}]
        
        # Determine log files
        if self.log_dir:
            from pathlib import Path
            log_dir = Path(self.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_filename = str(log_dir / f'{self.filename_prefix}.log')
            result_log_filename = str(log_dir / f'{self.filename_prefix[:-2]}rs.log')
        else:
            log_filename = f'{self.filename_prefix}.log'
            result_log_filename = f'{self.filename_prefix[:-2]}rs.log'
        
        # Call llm_call directly (it's already synchronous)
        response = llm_call(
            messages,
            model_index,
            log_filename,
            result_log_filename,
            system_prompt
        )
        
        return (response or "").replace('\u2019', "'")
    
    async def chat_with_messages(self, messages: List[Dict[str, Any]], model_index: int = None, system_prompt: str = '') -> str:
        """
        Async wrapper for chat with full message history.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model_index: Optional specific model to use
            system_prompt: Optional system prompt to prepend to conversation
            
        Returns:
            The LLM's response as a string
        """
        if model_index is None:
            model_index = self.current_model
            
        # Determine log files
        if self.log_dir:
            from pathlib import Path
            log_dir = Path(self.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_filename = str(log_dir / f'{self.filename_prefix}.log')
            result_log_filename = str(log_dir / f'{self.filename_prefix[:-2]}rs.log')
        else:
            log_filename = f'{self.filename_prefix}.log'
            result_log_filename = f'{self.filename_prefix[:-2]}rs.log'
            
        # Run the synchronous llm_call in a thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,  # Use default executor
            llm_call,
            messages,
            model_index,
            log_filename,
            result_log_filename,
            system_prompt
        )
        
        return (response or "").replace('\u2019', "'")