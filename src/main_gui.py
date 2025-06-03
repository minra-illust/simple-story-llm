import asyncio
import json
import os
import signal
import time
import sys
import threading
from pathlib import Path
from typing import Dict, Any, List
import yaml
from datetime import datetime

from system.world_loader import WorldLoader
from system.aida.simple_aida import SimpleAida
from system.narrations_processor import NarrationsProcessor
from system.chapter import Chapter, Part
from system.chapter_manager import ChapterManager
from gui import GameEngineGUI, GUIOutputRedirect

# Override print functions to work with GUI
class GUIPrintFunctions:
    def __init__(self, gui: GameEngineGUI):
        self.gui = gui
        
    def print_rich(self, text: str, end: str = "\n"):
        self.gui.write(text, end)
        
    def print_section_header(self, title: str):
        self.gui.write("\n")
        self.gui.write(f"[bold cyan]{'='*50}[/bold cyan]\n")
        self.gui.write(f"[bold cyan]{title.center(50)}[/bold cyan]\n")
        self.gui.write(f"[bold cyan]{'='*50}[/bold cyan]\n")
        self.gui.write("\n")
        
    def print_narrative(self, text: str):
        self.gui.write(text + "\n", is_narrative=True)


class GameEngineWithGUI:
    def __init__(self, card_name: str, gui: GameEngineGUI):
        self.card_name = card_name
        self.gui = gui
        self.print_funcs = GUIPrintFunctions(gui)
        
        # Initialize chapter manager
        self.chapter_manager = ChapterManager()
        self.chapter_manager.set_current_card(card_name)
        
        # Connect to GUI
        self.gui.chapter_manager = self.chapter_manager
        self.gui.generate_chapter_callback = self.generate_chapter
        self.gui.generate_part_callback = self.generate_single_part
        self.chapter_manager.add_change_callback(self.gui._refresh_chapter_list)
        
        # Initialize processors
        self.narrations_processor = NarrationsProcessor()
        
        # Initial UI update
        self.gui._refresh_chapter_list()
        
        # Async handling
        self.shutdown_event = asyncio.Event()
        self.current_tasks = set()
        
    
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
    
    def _parse_beats(self, user_input: str) -> List[Dict[str, str]]:
        """Parse user input into story beats.
        
        Returns:
            list: List of dicts with 'type' and 'content' for each beat
        """
        if '//' not in user_input:
            # Single input - treat as complete beat
            return [{'type': 'complete', 'content': user_input.strip()}]
        
        # Split by // and identify beat types
        parts = [part.strip() for part in user_input.split('//') if part.strip()]
        
        if len(parts) == 0:
            return []
        elif len(parts) == 1:
            return [{'type': 'complete', 'content': parts[0]}]
        elif len(parts) == 2:
            # Check if the last beat is the "!!" shortcut
            if parts[1] == "!!":
                parts[1] = "The beats finish with the success or failure of the character's actions based on the context"
            return [
                {'type': 'start', 'content': parts[0]},
                {'type': 'finish', 'content': parts[1]}
            ]
        else:
            beats = []
            beats.append({'type': 'start', 'content': parts[0]})
            for part in parts[1:-1]:
                beats.append({'type': 'middle', 'content': part})
            # Check if the last beat is the "!!" shortcut
            last_beat = parts[-1]
            if last_beat == "!!":
                last_beat = "The beats finish with the success or failure of the character's actions based on the context"
            beats.append({'type': 'finish', 'content': last_beat})
            return beats

    async def generate_chapter(self, chapter_id: str):
        """Generate all parts of a chapter sequentially"""
        chapter = self.chapter_manager.get_chapter(chapter_id)
        if not chapter:
            return
        
        # Get non-empty parts
        parts_to_generate = chapter.get_non_empty_parts()
        if not parts_to_generate:
            self.print_funcs.print_rich("[yellow]No parts with input to generate[/yellow]")
            return
        
        # Set chapter to generating state
        if chapter_id in self.gui.chapter_widgets:
            self.gui.chapter_widgets[chapter_id].set_generating(True)
        
        try:
            # Initialize AIDA for this chapter
            aida = SimpleAida(Path(f"cards/{self.card_name}"))
            
            # Accumulated key facts from previous parts
            accumulated_facts = []
            
            for i, part in enumerate(parts_to_generate):
                self.print_funcs.print_section_header(f"Generating Part {part.number}")
                
                # Set part to generating state
                if chapter_id in self.gui.chapter_widgets:
                    self.gui.chapter_widgets[chapter_id].set_part_generating(part.id, True)
                
                # Build context from previous parts in this chapter
                log_context = []
                for prev_part in parts_to_generate[:i]:
                    if prev_part.is_generated and prev_part.processed_log:
                        log_entry = {
                            'user_input': prev_part.user_input,
                            'narration_log': prev_part.narration_log,
                            **prev_part.processed_log
                        }
                        log_context.append(log_entry)
                
                # Load characters from card
                world_loader = WorldLoader(Path(f"cards/{self.card_name}"))
                characters = world_loader._load_characters()
                
                # Prepare world data from chapter
                world_data = {
                    'story_initial_context': chapter.opening_summary,
                    'places': chapter.places,
                    'facts': chapter.facts,
                    'vocabulary_guidance': chapter.vocabulary_guidance,
                    'characters': characters
                }
                
                # Parse beats
                beats = self._parse_beats(part.user_input)
                
                # Generate with context of all parts
                all_parts_input = [(p.number, p.user_input) for p in parts_to_generate]
                
                self.print_funcs.print_rich(f"[yellow]Generating part {part.number} of {len(parts_to_generate)}...[/yellow]")
                
                # Create modified generate method that includes all parts
                narrative_task = asyncio.create_task(
                    self._generate_part_with_context(
                        aida, world_data, log_context, beats, 
                        part.number, all_parts_input
                    )
                )
                self.current_tasks.add(narrative_task)
                
                try:
                    result = await narrative_task
                finally:
                    self.current_tasks.discard(narrative_task)
                
                # Process the narrative
                part.narration_log = self._extract_narration_log(result['narrative'])
                
                # Extract key information
                processed = self.narrations_processor.process(
                    narrative=result['narrative'],
                    world_data=world_data,
                    user_input=part.user_input,
                    log_history=log_context
                )
                
                part.processed_log = {
                    'summary': processed.get('summary', ''),
                    'key_facts': processed.get('key_facts', []),
                    'character_states': processed.get('character_states', {}),
                    'location': processed.get('location', '')
                }
                part.is_generated = True
                part.generation_timestamp = datetime.now().isoformat()
                
                # Save progress immediately after part generation
                self.chapter_manager.save_to_runtime(immediate=True)
                
                # Update UI
                if chapter_id in self.gui.chapter_widgets:
                    self.gui.chapter_widgets[chapter_id].set_part_generating(part.id, False)
                
                # Update narration log view if this chapter is selected
                if self.gui.current_chapter_id == chapter_id:
                    self.gui._update_narration_log_tab()
                
                
                self.print_funcs.print_rich(f"[green]Part {part.number} completed[/green]\n")
            
            # Mark chapter as generated
            chapter.is_generated = True
            self.chapter_manager.save_to_runtime(immediate=True)
            
            self.print_funcs.print_rich("[bold green]Chapter generation completed![/bold green]")
            
        except Exception as e:
            self.print_funcs.print_rich(f"[red]Error generating chapter: {e}[/red]")
            import traceback
            traceback.print_exc()
        finally:
            # Reset visual state
            if chapter_id in self.gui.chapter_widgets:
                self.gui.chapter_widgets[chapter_id].set_generating(False)
    
    async def generate_single_part(self, chapter_id: str, part_id: str):
        """Generate a single part of a chapter"""
        chapter = self.chapter_manager.get_chapter(chapter_id)
        if not chapter:
            return
        
        # Find the specific part
        part_to_generate = None
        for part in chapter.parts:
            if part.id == part_id:
                part_to_generate = part
                break
        
        if not part_to_generate or not part_to_generate.user_input.strip():
            self.print_funcs.print_rich("[yellow]Part has no input to generate[/yellow]")
            return
        
        # Set part to generating state
        if chapter_id in self.gui.chapter_widgets:
            self.gui.chapter_widgets[chapter_id].set_part_generating(part_id, True)
        
        try:
            self.print_funcs.print_section_header(f"Generating Part {part_to_generate.number}")
            
            # Initialize AIDA for this chapter
            aida = SimpleAida(Path(f"cards/{self.card_name}"))
            
            # Build context from previous parts in this chapter (only generated ones)
            log_context = []
            for prev_part in chapter.parts:
                if prev_part.number < part_to_generate.number and prev_part.is_generated and prev_part.processed_log:
                    log_entry = {
                        'user_input': prev_part.user_input,
                        'narration_log': prev_part.narration_log,
                        **prev_part.processed_log
                    }
                    log_context.append(log_entry)
            
            # Load characters from card
            world_loader = WorldLoader(Path(f"cards/{self.card_name}"))
            characters = world_loader._load_characters()
            
            # Prepare world data from chapter
            world_data = {
                'story_initial_context': chapter.opening_summary,
                'places': chapter.places,
                'facts': chapter.facts,
                'vocabulary_guidance': chapter.vocabulary_guidance,
                'characters': characters
            }
            
            # Parse beats
            beats = self._parse_beats(part_to_generate.user_input)
            
            # Generate with context of all parts
            all_parts_input = [(p.number, p.user_input) for p in chapter.parts if p.user_input.strip()]
            
            self.print_funcs.print_rich(f"[yellow]Generating part {part_to_generate.number}...[/yellow]")
            
            # Create modified generate method that includes all parts
            narrative_task = asyncio.create_task(
                self._generate_part_with_context(
                    aida, world_data, log_context, beats, 
                    part_to_generate.number, all_parts_input
                )
            )
            self.current_tasks.add(narrative_task)
            
            try:
                result = await narrative_task
            finally:
                self.current_tasks.discard(narrative_task)
            
            # Process the narrative
            part_to_generate.narration_log = self._extract_narration_log(result['narrative'])
            
            # Extract key information
            processed = self.narrations_processor.process(
                narrative=result['narrative'],
                world_data=world_data,
                user_input=part_to_generate.user_input,
                log_history=log_context
            )
            
            part_to_generate.processed_log = {
                'summary': processed.get('summary', ''),
                'key_facts': processed.get('key_facts', []),
                'character_states': processed.get('character_states', {}),
                'location': processed.get('location', '')
            }
            part_to_generate.is_generated = True
            part_to_generate.generation_timestamp = datetime.now().isoformat()
            
            # Save progress immediately after part generation
            self.chapter_manager.save_to_runtime(immediate=True)
            
            # Update narration log view if this chapter is selected
            if self.gui.current_chapter_id == chapter_id:
                self.gui._update_narration_log_tab()
            
            self.print_funcs.print_rich(f"[green]Part {part_to_generate.number} completed[/green]\n")
            
        except Exception as e:
            self.print_funcs.print_rich(f"[red]Error generating part: {e}[/red]")
            import traceback
            traceback.print_exc()
        finally:
            # Reset visual state
            if chapter_id in self.gui.chapter_widgets:
                self.gui.chapter_widgets[chapter_id].set_part_generating(part_id, False)
    
    async def _generate_part_with_context(self, aida, world_data, log_context, 
                                        beats, part_number, all_parts):
        """Modified generate that includes all parts in the prompt"""
        # Build a modified prompt that includes all parts
        sections = []
        sections.append("\n## All Chapter Parts\n")
        sections.append("This chapter consists of the following parts:\n")
        for num, input_text in all_parts:
            if num == part_number:
                sections.append(f"**Part {num} (CURRENT)**: {input_text}\n")
            else:
                sections.append(f"Part {num}: {input_text}\n")
        sections.append(f"\nYou are currently generating Part {part_number}.\n")
        
        # Temporarily modify the world data to include this context
        modified_world_data = world_data.copy()
        modified_world_data['chapter_context'] = "".join(sections)
        
        # Call the original generate method
        return await aida.generate(
            world_data=modified_world_data,
            log_context=log_context,
            beats=beats,
            part_number=part_number
        )
    
    async def run_part(self, user_input: str) -> Dict[str, Any]:
        self.print_funcs.print_section_header("Processing Part")
        
        # Parse beats
        beats = self._parse_beats(user_input)
        
        if not beats:
            self.print_funcs.print_rich("[red]No beats provided[/red]")
            return None
        
        # Reload log history from file to ensure we have the latest data
        self.log_history = self._load_log_history()
        
        # Calculate part number
        part_number = len(self.log_history) + 1
        
        # Load world data from file every time
        world_data = self.world_loader.load_all()
        
        # Get relevant log context based on part number
        log_context = self._get_context_for_part(self.log_history, part_number)
        
        # Generate narrative with Aida
        self.print_funcs.print_rich(f"[yellow]Generating narrative for part {part_number}...[/yellow]")
        self.print_funcs.print_rich(f"[dim]Beats: {len(beats)} ({', '.join(b['type'] for b in beats)})[/dim]")
        
        # Create cancellable task for narrative generation
        narrative_task = asyncio.create_task(self.aida.generate(
            world_data=world_data,
            log_context=log_context,
            beats=beats,
            part_number=part_number
        ))
        self.current_tasks.add(narrative_task)
        
        try:
            # Wait for either the task to complete or shutdown
            done, pending = await asyncio.wait(
                [narrative_task, asyncio.create_task(self.shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Check if shutdown was requested
            if self.shutdown_event.is_set():
                narrative_task.cancel()
                try:
                    await narrative_task
                except asyncio.CancelledError:
                    pass
                raise asyncio.CancelledError("Part cancelled due to shutdown")
            
            result = narrative_task.result()
        finally:
            self.current_tasks.discard(narrative_task)
        
        # Extract and display the NARRATION_LOG
        self.print_funcs.print_section_header("Narration Log")
        narration_log = self._extract_narration_log(result['narrative'])
        if narration_log is not None:
            self.print_funcs.print_narrative(narration_log)
        else:
            self.print_funcs.print_rich("[red]ERROR: Could not find NARRATION_LOG in narrative output[/red]")
            self.print_funcs.print_narrative(result['narrative'])   # Fallback: show full narrative
        
        # Process log directly (synchronously)
        self.print_funcs.print_rich("[yellow]...[/yellow]")
        self.print_funcs.print_rich("[dim]Extracting key information from narrative...[/dim]")
        try:
            # Process the narrative to extract key information
            processed_log = self.narrations_processor.process(
                narrative=result['narrative'],
                world_data=world_data,
                user_input=user_input,  # Keep original user input for log
                log_history=self.log_history
            )
            
            # Add processed log to history and save immediately
            self.log_history.append(processed_log)
            self._save_log_history()
            
            # Update part prompt for next part
            self._update_part_prompt()
            
            
        except Exception as e:
            self.print_funcs.print_rich(f"[red]Processing failed: {e}[/red]")
            # Create fallback log entry
            narration_log = self._extract_narration_log(result['narrative'])
            fallback_log = {
                'timestamp': datetime.now().isoformat(),
                'user_input': user_input,
                'summary': f"Part {part_number}: {user_input[:50]}...",
                'key_facts': [],
                'character_states': {},
                'location': '',
                'narrative_snippet': result['narrative'][:200] + '...' if len(result['narrative']) > 200 else result['narrative'],
                'narration_log': narration_log if narration_log else result['narrative']
            }
            self.log_history.append(fallback_log)
            self._save_log_history()
            
            # Update part prompt for next part
            self._update_part_prompt()
        
        return result
    
    
    async def shutdown(self):
        """Clean shutdown of all tasks and background processes."""
        self.print_funcs.print_rich("\n[yellow]Shutting down...[/yellow]")
        
        # Signal shutdown to all tasks
        self.shutdown_event.set()
        
        # Cancel all current tasks
        if self.current_tasks:
            self.print_funcs.print_rich("[yellow]Cancelling active tasks...[/yellow]")
            for task in list(self.current_tasks):
                task.cancel()
            
            # Wait for tasks to be cancelled
            if self.current_tasks:
                await asyncio.gather(*self.current_tasks, return_exceptions=True)
        
        # Shutdown chapter manager to ensure saves complete
        if self.chapter_manager:
            self.chapter_manager.shutdown()
        
        self.print_funcs.print_rich("[yellow]Goodbye![/yellow]")

    async def run(self):
        """Modified run method without input loop"""
        self.print_funcs.print_rich(f"[bold green]Chapter-based Story Engine[/bold green]")
        self.print_funcs.print_rich(f"[dim]Card: {self.card_name}[/dim]")
        self.print_funcs.print_rich("")
        
        try:
            # Just wait for shutdown
            await self.shutdown_event.wait()
        except Exception as e:
            self.print_funcs.print_rich(f"[red]Fatal error: {e}[/red]")
        finally:
            await self.shutdown()
    




def run_gui_with_async():
    """Run GUI with async game engine"""
    import asyncio
    import threading
    from concurrent.futures import Future
    
    # Create GUI first
    gui = GameEngineGUI()
    gui_print = GUIPrintFunctions(gui)
    
    # Redirect stdout
    sys.stdout = GUIOutputRedirect(gui)
    
    # Create event loop for async operations
    loop = asyncio.new_event_loop()
    
    # Flag to signal when to stop
    stop_event = threading.Event()
    
    async def async_game_loop():
        """Async game loop that runs in separate thread"""
        try:
            # Set the event loop on the GUI
            gui.set_event_loop(loop)
            
            gui_print.print_rich("[bold cyan]Chapter-based Story Engine[/bold cyan]")
            gui_print.print_rich("")
            
            # For now, still do card selection at startup
            # Later this will be moved to a menu
            cards_dir = Path("cards")
            cards = [d.name for d in cards_dir.iterdir() if d.is_dir()]
            
            if not cards:
                gui_print.print_rich("[red]No cards found in cards/ directory[/red]")
                return
            
            # Create a game engine instance
            engine = None
            current_card = None
            
            def on_card_select(card_name):
                nonlocal engine, current_card
                if current_card == card_name:
                    return  # Already selected
                
                current_card = card_name
                gui_print.print_rich(f"\n[bold]Switching to card: {card_name}[/bold]\n")
                
                # Create new engine with selected card
                if engine:
                    # Clean up previous engine if exists
                    asyncio.create_task(engine.shutdown())
                
                engine = GameEngineWithGUI(card_name, gui)
            
            # Populate card menu
            gui.populate_card_menu(cards, on_card_select)
            
            # Auto-select first card
            on_card_select(cards[0])
            
            try:
                await engine.run()
            except Exception as e:
                gui_print.print_rich(f"[red]Fatal error: {e}[/red]")
                await engine.shutdown()
        finally:
            stop_event.set()
            gui.root.quit()
    
    def run_async_thread():
        """Run async game in separate thread"""
        asyncio.set_event_loop(loop)
        loop.run_until_complete(async_game_loop())
    
    # Start async thread
    async_thread = threading.Thread(target=run_async_thread, daemon=True)
    async_thread.start()
    
    # Run GUI in main thread
    gui.run()
    
    # Cleanup
    stop_event.set()
    loop.call_soon_threadsafe(loop.stop)
    async_thread.join(timeout=2)


if __name__ == "__main__":
    try:
        run_gui_with_async()
    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()