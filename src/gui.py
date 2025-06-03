try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, font
except ImportError:
    print("Error: tkinter is not available. Please install python3-tk package.")
    print("On Ubuntu/Debian: sudo apt-get install python3-tk")
    print("On Fedora: sudo dnf install python3-tkinter")
    print("On macOS: tkinter should be included with Python")
    sys.exit(1)

import asyncio
import threading
import queue
import re
import sys
import os
from typing import Callable, Optional, List, Tuple, Dict, Set
from pathlib import Path
from system.chapter import Chapter, Part


class GameEngineGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Game Engine")
        self.root.geometry("1200x750")
        
        # Dark theme colors
        self.bg_color = "#1a1a1a"
        self.fg_color = "#e0e0e0"
        self.input_bg = "#2a2a2a"
        self.input_fg = "#ffffff"
        self.border_color = "#444444"
        
        # Configure root window
        self.root.configure(bg=self.bg_color)
        
        # Create menu bar
        self.menubar = tk.Menu(self.root, bg=self.bg_color, fg=self.fg_color)
        self.root.config(menu=self.menubar)
        
        # Card menu
        self.card_menu = tk.Menu(self.menubar, tearoff=0, bg=self.input_bg, fg=self.fg_color)
        self.menubar.add_cascade(label="Card", menu=self.card_menu)
        
        # Queue for thread-safe GUI updates
        self.output_queue = queue.Queue()
        self.input_queue = queue.Queue()
        
        # Input callback and event
        self.input_callback: Optional[Callable] = None
        self.input_event = None  # Will be set when loop is available
        self.current_input = ""
        self.loop = None  # Will store the async loop
        
        # View management
        self.current_view = "Main"
        self.view_frames: Dict[str, tk.Frame] = {}
        self.log_watchers: Dict[str, Dict] = {}
        self.log_update_queue = queue.Queue()
        
        # Chapter management
        self.chapter_widgets: Dict[str, 'ChapterWidget'] = {}
        self.part_input_widgets: Dict[str, 'PartInputWidget'] = {}
        self.current_chapter_id = None
        self.chapter_manager = None  # Will be set by main
        
        # Track active tags for proper formatting
        self.active_tags = []
        
        # Setup GUI components
        self._setup_ui()
        self._setup_tags()
        
        # Start processing queue
        self._process_output_queue()
        self._process_log_updates()
        
    def _setup_ui(self):
        # Top frame for view buttons
        top_frame = tk.Frame(self.root, bg=self.bg_color)
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        # View buttons
        views = ["Main", "Aida Calls", "Narration Processor Calls"]
        self.view_buttons = {}
        for view in views:
            btn = tk.Button(
                top_frame,
                text=view,
                bg=self.input_bg,
                fg=self.fg_color,
                font=("Consolas", 10),
                relief=tk.FLAT,
                padx=15,
                pady=5,
                command=lambda v=view: self._switch_view(v)
            )
            btn.pack(side=tk.LEFT, padx=(0, 5))
            self.view_buttons[view] = btn
        
        # Highlight current view
        self.view_buttons[self.current_view].configure(bg="#4a4a4a")
        
        # Main container frame that will hold all views
        self.container_frame = tk.Frame(self.root, bg=self.bg_color)
        self.container_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create frames for each view
        self._create_main_view()
        self._create_log_view("Aida Calls", "_llm_call_simple_aida")
        self._create_log_view("Narration Processor Calls", "_llm_call_narrations_processor")
        
        # Show initial view
        self._show_view(self.current_view)
    def _create_main_view(self):
        """Create the main view with sidebar"""
        main_frame = tk.Frame(self.container_frame, bg=self.bg_color)
        self.view_frames["Main"] = main_frame
        
        # Create horizontal paned window
        self.main_paned = tk.PanedWindow(
            main_frame,
            orient=tk.HORIZONTAL,
            bg=self.bg_color,
            sashwidth=5,
            sashrelief=tk.RIDGE
        )
        self.main_paned.pack(fill=tk.BOTH, expand=True)
        
        # Left sidebar for chapters
        self._create_chapter_sidebar()
        
        # Right content area
        self._create_content_area()
        
        # Create a hidden text widget for general output
        self.narration_log = tk.Text(main_frame, height=1, width=1)
        self._setup_output_tags()
        
        # Set initial sash position
        self.main_paned.update()
        self.main_paned.sash_place(0, 300, 0)
    
    def _create_chapter_sidebar(self):
        """Create the chapter sidebar"""
        sidebar_frame = tk.Frame(self.main_paned, bg=self.bg_color, width=300)
        sidebar_frame.pack_propagate(False)
        
        # Header
        header_label = tk.Label(
            sidebar_frame,
            text="Chapters",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Consolas", 14, "bold")
        )
        header_label.pack(pady=10)
        
        # Scrollable area for chapters
        self.chapter_canvas = tk.Canvas(sidebar_frame, bg=self.bg_color, highlightthickness=0)
        chapter_scrollbar = tk.Scrollbar(sidebar_frame, orient="vertical", command=self.chapter_canvas.yview)
        self.chapter_list_frame = tk.Frame(self.chapter_canvas, bg=self.bg_color)
        
        self.chapter_canvas.configure(yscrollcommand=chapter_scrollbar.set)
        canvas_window = self.chapter_canvas.create_window((0, 0), window=self.chapter_list_frame, anchor="nw")
        
        self.chapter_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chapter_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure scroll region updates
        def configure_scroll_region(e=None):
            self.chapter_canvas.configure(scrollregion=self.chapter_canvas.bbox("all"))
        self.chapter_list_frame.bind("<Configure>", configure_scroll_region)
        
        # Configure canvas window width to match canvas width
        def configure_canvas_width(e=None):
            canvas_width = self.chapter_canvas.winfo_width()
            self.chapter_canvas.itemconfig(canvas_window, width=canvas_width)
        self.chapter_canvas.bind("<Configure>", configure_canvas_width)
        
        # Bind mouse wheel to canvas for scrolling
        def on_mousewheel(event):
            self.chapter_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Function to bind mouse wheel to all widgets recursively
        def bind_mousewheel_to_widget(widget):
            widget.bind("<MouseWheel>", on_mousewheel)  # Windows
            widget.bind("<Button-4>", lambda e: self.chapter_canvas.yview_scroll(-1, "units"))  # Linux
            widget.bind("<Button-5>", lambda e: self.chapter_canvas.yview_scroll(1, "units"))   # Linux
            
            # Bind to all children
            for child in widget.winfo_children():
                bind_mousewheel_to_widget(child)
        
        # Bind mouse wheel events to canvas and its contents
        bind_mousewheel_to_widget(self.chapter_canvas)
        bind_mousewheel_to_widget(self.chapter_list_frame)
        
        # Store the binding function to use when new widgets are added
        self.bind_mousewheel_to_widget = bind_mousewheel_to_widget
        
        # Right-click menu for empty space
        self.sidebar_menu = tk.Menu(self.chapter_canvas, tearoff=0, bg=self.input_bg, fg=self.fg_color)
        self.sidebar_menu.add_command(label="Create Chapter", command=self._create_new_chapter)
        
        # Bind right-click
        self.chapter_canvas.bind("<Button-3>", self._show_sidebar_menu)
        
        self.main_paned.add(sidebar_frame)
    
    def _create_content_area(self):
        """Create the tabbed content area"""
        content_frame = tk.Frame(self.main_paned, bg=self.bg_color)
        
        # Create notebook for tabs
        style = ttk.Style()
        style.theme_use('default')
        style.configure('Dark.TNotebook', background=self.bg_color)
        style.configure('Dark.TNotebook.Tab', 
                       background=self.input_bg,
                       foreground=self.fg_color,
                       padding=[20, 10])
        style.map('Dark.TNotebook.Tab',
                 background=[('selected', '#4a4a4a')])
        
        self.content_notebook = ttk.Notebook(content_frame, style='Dark.TNotebook')
        
        # Tab 1: Chapter editing
        self._create_chapter_edit_tab()
        
        # Tab 2: Narration log
        self._create_narration_log_tab()
        
        # Bind F1/F2 keys
        self.root.bind('<F1>', lambda e: self.content_notebook.select(0))
        self.root.bind('<F2>', lambda e: self.content_notebook.select(1))
        
        # Initially hide the notebook since no chapter is selected
        self._update_tabs_visibility()
        
        self.main_paned.add(content_frame)
    
    def _create_chapter_edit_tab(self):
        """Create the chapter editing tab"""
        edit_frame = tk.Frame(self.content_notebook, bg=self.bg_color)
        
        # Scrollable container
        edit_canvas = tk.Canvas(edit_frame, bg=self.bg_color, highlightthickness=0)
        edit_scrollbar = tk.Scrollbar(edit_frame, orient="vertical", command=edit_canvas.yview)
        self.edit_container = tk.Frame(edit_canvas, bg=self.bg_color)
        
        edit_canvas.configure(yscrollcommand=edit_scrollbar.set)
        canvas_window = edit_canvas.create_window((0, 0), window=self.edit_container, anchor="nw")
        
        edit_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        edit_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create text areas
        mono_font = font.Font(family="Consolas", size=11)
        
        # Opening Summary
        tk.Label(self.edit_container, text="Opening Summary", 
                 bg=self.bg_color, fg=self.fg_color, 
                 font=("Consolas", 12, "bold")).pack(pady=(10, 5), anchor="w", padx=10)
        
        self.opening_summary_text = tk.Text(
            self.edit_container,
            bg="#2a2a2a",
            fg=self.fg_color,
            font=mono_font,
            height=8,
            wrap=tk.WORD,
            padx=10,
            pady=10
        )
        self.opening_summary_text.pack(fill=tk.X, padx=10, pady=(0, 20))
        self.opening_summary_text.bind('<KeyRelease>', self._on_chapter_data_change)
        
        # Places
        tk.Label(self.edit_container, text="Places", 
                 bg=self.bg_color, fg=self.fg_color, 
                 font=("Consolas", 12, "bold")).pack(pady=(10, 5), anchor="w", padx=10)
        
        self.places_text = tk.Text(
            self.edit_container,
            bg="#2a2a2a",
            fg=self.fg_color,
            font=mono_font,
            height=8,
            wrap=tk.WORD,
            padx=10,
            pady=10
        )
        self.places_text.pack(fill=tk.X, padx=10, pady=(0, 20))
        self.places_text.bind('<KeyRelease>', self._on_chapter_data_change)
        
        # Facts
        tk.Label(self.edit_container, text="Facts", 
                 bg=self.bg_color, fg=self.fg_color, 
                 font=("Consolas", 12, "bold")).pack(pady=(10, 5), anchor="w", padx=10)
        
        self.facts_text = tk.Text(
            self.edit_container,
            bg="#2a2a2a",
            fg=self.fg_color,
            font=mono_font,
            height=8,
            wrap=tk.WORD,
            padx=10,
            pady=10
        )
        self.facts_text.pack(fill=tk.X, padx=10, pady=(0, 20))
        self.facts_text.bind('<KeyRelease>', self._on_chapter_data_change)
        
        # Vocabulary Guidance
        tk.Label(self.edit_container, text="Vocabulary Guidance", 
                 bg=self.bg_color, fg=self.fg_color, 
                 font=("Consolas", 12, "bold")).pack(pady=(10, 5), anchor="w", padx=10)
        
        self.vocabulary_text = tk.Text(
            self.edit_container,
            bg="#2a2a2a",
            fg=self.fg_color,
            font=mono_font,
            height=8,
            wrap=tk.WORD,
            padx=10,
            pady=10
        )
        self.vocabulary_text.pack(fill=tk.X, padx=10, pady=(0, 20))
        self.vocabulary_text.bind('<KeyRelease>', self._on_chapter_data_change)
        
        # Update scroll region
        def update_scroll_region(e=None):
            edit_canvas.configure(scrollregion=edit_canvas.bbox("all"))
        self.edit_container.bind("<Configure>", update_scroll_region)
        
        self.content_notebook.add(edit_frame, text="Chapter Edit (F1)")
    
    def _create_narration_log_tab(self):
        """Create the narration log tab"""
        log_frame = tk.Frame(self.content_notebook, bg=self.bg_color)
        
        # Create scrolled text for combined narration log
        mono_font = font.Font(family="Consolas", size=11)
        
        self.combined_narration_log = scrolledtext.ScrolledText(
            log_frame,
            bg=self.bg_color,
            fg=self.fg_color,
            font=mono_font,
            wrap=tk.WORD,
            padx=10,
            pady=10,
            state=tk.DISABLED
        )
        self.combined_narration_log.pack(fill=tk.BOTH, expand=True)
        
        # Configure tags for formatting
        self._setup_narration_tags(self.combined_narration_log)
        
        self.content_notebook.add(log_frame, text="Narration Log (F2)")
        
    def _setup_tags(self):
        """Setup text tags for colored output"""
        # We'll setup tags when needed on specific widgets
        pass
    
    def _setup_output_tags(self):
        """Setup text tags for the hidden output widget"""
        self.narration_log.tag_configure("red", foreground="#ff6b6b")
        self.narration_log.tag_configure("green", foreground="#51cf66")
        self.narration_log.tag_configure("yellow", foreground="#ffd93d")
        self.narration_log.tag_configure("blue", foreground="#6bcfff")
        self.narration_log.tag_configure("cyan", foreground="#4ecdc4")
        self.narration_log.tag_configure("magenta", foreground="#ff6b9d")
        self.narration_log.tag_configure("bold", font=("Consolas", 11, "bold"))
        self.narration_log.tag_configure("dim", foreground="#888888")
        self.narration_log.tag_configure("bold_green", foreground="#51cf66", font=("Consolas", 11, "bold"))
        self.narration_log.tag_configure("bold_cyan", foreground="#4ecdc4", font=("Consolas", 11, "bold"))
        self.narration_log.tag_configure("quote", foreground="#87ceeb")
        self.narration_log.tag_configure("character", foreground="#daa520")
        self.narration_log.tag_configure("angle_left", foreground="#ffa500")
        self.narration_log.tag_configure("angle_right", foreground="#51cf66")
        
            
    def set_input_callback(self, callback: Callable):
        """Set the callback for handling user input"""
        self.input_callback = callback
        
    def write(self, text: str, end: str = "\n", is_narrative: bool = False):
        """Thread-safe write to narration log"""
        self.output_queue.put((text, end, is_narrative))
        
    def _process_output_queue(self):
        """Process output queue for thread-safe GUI updates"""
        try:
            while True:
                try:
                    item = self.output_queue.get_nowait()
                    if len(item) == 3:
                        text, end, is_narrative = item
                        self._write_to_log(text, end, is_narrative)
                    else:
                        text, end = item
                        self._write_to_log(text, end, False)
                except queue.Empty:
                    break
        except Exception as e:
            print(f"Error processing output queue: {e}")
        finally:
            self.root.after(50, self._process_output_queue)
            
    def _write_to_log(self, text: str, end: str, is_narrative: bool = False):
        """Write text to the narration log with formatting"""
        self.narration_log.configure(state=tk.NORMAL)
        
        # Write formatted text
        self._write_formatted_text(text, is_narrative)
        
        if end:
            self.narration_log.insert(tk.END, end)
            
        self.narration_log.configure(state=tk.DISABLED)
        self.narration_log.see(tk.END)
        
    def _write_formatted_text(self, text: str, is_narrative: bool = False):
        """Write text with proper formatting tags"""
        # Tag mappings
        tag_map = {
            '[red]': ('red', True),
            '[/red]': ('red', False),
            '[green]': ('green', True),
            '[/green]': ('green', False),
            '[yellow]': ('yellow', True),
            '[/yellow]': ('yellow', False),
            '[blue]': ('blue', True),
            '[/blue]': ('blue', False),
            '[cyan]': ('cyan', True),
            '[/cyan]': ('cyan', False),
            '[magenta]': ('magenta', True),
            '[/magenta]': ('magenta', False),
            '[bold]': ('bold', True),
            '[/bold]': ('bold', False),
            '[dim]': ('dim', True),
            '[/dim]': ('dim', False),
            '[bold green]': ('bold_green', True),
            '[/bold green]': ('bold_green', False),
            '[bold cyan]': ('bold_cyan', True),
            '[/bold cyan]': ('bold_cyan', False),
        }
        
        i = 0
        current_tags = list(self.active_tags)  # Inherit active tags
        
        # For narrative text, also handle special patterns
        in_quotes = False
        
        while i < len(text):
            # Check for formatting tags
            tag_found = False
            for tag_text, (tag_name, is_start) in tag_map.items():
                if text[i:].startswith(tag_text):
                    if is_start:
                        if tag_name not in current_tags:
                            current_tags.append(tag_name)
                    else:
                        if tag_name in current_tags:
                            current_tags.remove(tag_name)
                    i += len(tag_text)
                    tag_found = True
                    break
            
            if tag_found:
                continue
            
            # Handle narrative-specific formatting
            if is_narrative:
                # Character names in [{name}]
                if text[i:i+2] == '[{' and '}]' in text[i:]:
                    end_idx = text.find('}]', i)
                    if end_idx != -1:
                        char_text = text[i:end_idx + 2]
                        self.narration_log.insert(tk.END, char_text, 'character')
                        i = end_idx + 2
                        continue
                
                # Quotes
                elif text[i] == '"':
                    if in_quotes:
                        self.narration_log.insert(tk.END, text[i])
                        in_quotes = False
                    else:
                        in_quotes = True
                        self.narration_log.insert(tk.END, text[i], 'quote')
                    i += 1
                    continue
                
                # Angle brackets
                elif text[i] == '<':
                    self.narration_log.insert(tk.END, text[i], 'angle_left')
                    i += 1
                    continue
                elif text[i] == '>':
                    self.narration_log.insert(tk.END, text[i], 'angle_right')
                    i += 1
                    continue
            
            # Regular character with current tags
            tags_to_apply = list(current_tags)
            if is_narrative and in_quotes:
                tags_to_apply.append('quote')
            
            if tags_to_apply:
                self.narration_log.insert(tk.END, text[i], tuple(tags_to_apply))
            else:
                self.narration_log.insert(tk.END, text[i])
            i += 1
        
        # Update active tags for next write
        self.active_tags = current_tags
        
    
    
    
    
    def clear_log(self):
        """Clear the narration log"""
        self.narration_log.configure(state=tk.NORMAL)
        self.narration_log.delete(1.0, tk.END)
        self.narration_log.configure(state=tk.DISABLED)
        
    def run(self):
        """Start the GUI main loop"""
        self.root.mainloop()
        
    def set_event_loop(self, loop):
        """Set the async event loop and create the input event"""
        self.loop = loop
        self.input_event = asyncio.Event()
        
    async def get_input(self) -> str:
        """Async method to get user input"""
        if not self.input_event:
            raise RuntimeError("Event loop not set. Call set_event_loop first.")
        self.input_event.clear()
        await self.input_event.wait()
        input_value = self.current_input
        self.current_input = ""
        return input_value
        
    def close(self):
        """Close the GUI window"""
        self.root.quit()
        self.root.destroy()
    
    def _create_log_view(self, view_name: str, log_prefix: str):
        """Create a log view with side-by-side request/response containers"""
        view_frame = tk.Frame(self.container_frame, bg=self.bg_color)
        self.view_frames[view_name] = view_frame
        
        # Create mono font
        mono_font = font.Font(family="Consolas", size=11)
        
        # Create paned window for resizable split
        paned_window = tk.PanedWindow(
            view_frame,
            orient=tk.HORIZONTAL,
            bg=self.bg_color,
            sashwidth=5,
            sashrelief=tk.RIDGE
        )
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Left side - Request log
        left_frame = tk.Frame(paned_window, bg=self.bg_color)
        left_label = tk.Label(
            left_frame,
            text="Request",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Consolas", 12, "bold")
        )
        left_label.pack(pady=(0, 5))
        
        request_text = scrolledtext.ScrolledText(
            left_frame,
            bg=self.bg_color,
            fg=self.fg_color,
            font=mono_font,
            wrap=tk.WORD,
            padx=10,
            pady=10,
            insertbackground=self.fg_color,
            selectbackground="#4a4a4a",
            selectforeground=self.fg_color,
            relief=tk.FLAT,
            borderwidth=1
        )
        request_text.pack(fill=tk.BOTH, expand=True)
        request_text.configure(state=tk.DISABLED)
        
        # Configure scrollbar colors
        request_text.vbar.configure(
            bg=self.input_bg,
            troughcolor=self.bg_color,
            activebackground="#555555"
        )
        
        paned_window.add(left_frame)
        
        # Right side - Response log
        right_frame = tk.Frame(paned_window, bg=self.bg_color)
        right_label = tk.Label(
            right_frame,
            text="Response",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Consolas", 12, "bold")
        )
        right_label.pack(pady=(0, 5))
        
        response_text = scrolledtext.ScrolledText(
            right_frame,
            bg=self.bg_color,
            fg=self.fg_color,
            font=mono_font,
            wrap=tk.WORD,
            padx=10,
            pady=10,
            insertbackground=self.fg_color,
            selectbackground="#4a4a4a",
            selectforeground=self.fg_color,
            relief=tk.FLAT,
            borderwidth=1
        )
        response_text.pack(fill=tk.BOTH, expand=True)
        response_text.configure(state=tk.DISABLED)
        
        # Configure scrollbar colors
        response_text.vbar.configure(
            bg=self.input_bg,
            troughcolor=self.bg_color,
            activebackground="#555555"
        )
        
        paned_window.add(right_frame)
        
        # Set initial sash position to middle
        paned_window.update()
        paned_window.sash_place(0, paned_window.winfo_width() // 2, 0)
        
        # Store references and start watching log files
        self.log_watchers[view_name] = {
            'prefix': log_prefix,
            'request_text': request_text,
            'response_text': response_text,
            'request_file': f"{log_prefix}_rq.log",
            'response_file': f"{log_prefix}_rs.log",
            'request_mtime': 0,
            'response_mtime': 0
        }
    
    def _switch_view(self, view_name: str):
        """Switch to a different view"""
        if view_name == self.current_view:
            return
        
        # Update button states
        self.view_buttons[self.current_view].configure(bg=self.input_bg)
        self.view_buttons[view_name].configure(bg="#4a4a4a")
        
        # Hide current view
        self._hide_view(self.current_view)
        
        # Show new view
        self._show_view(view_name)
        
        self.current_view = view_name
    
    def _show_view(self, view_name: str):
        """Show a specific view"""
        if view_name in self.view_frames:
            self.view_frames[view_name].pack(fill=tk.BOTH, expand=True)
            
            # If it's a log view, update the log contents
            if view_name in self.log_watchers:
                self._update_log_view(view_name)
    
    def _hide_view(self, view_name: str):
        """Hide a specific view"""
        if view_name in self.view_frames:
            self.view_frames[view_name].pack_forget()
    
    def _update_log_view(self, view_name: str):
        """Update the contents of a log view"""
        watcher = self.log_watchers.get(view_name)
        if not watcher:
            return
        
        # Check request file
        request_path = Path(watcher['request_file'])
        if request_path.exists():
            try:
                mtime = request_path.stat().st_mtime
                if mtime > watcher['request_mtime']:
                    watcher['request_mtime'] = mtime
                    content = request_path.read_text(encoding='utf-8', errors='replace')
                    self._update_text_widget(watcher['request_text'], content)
            except Exception as e:
                print(f"Error reading request file: {e}")
        
        # Check response file
        response_path = Path(watcher['response_file'])
        if response_path.exists():
            try:
                mtime = response_path.stat().st_mtime
                if mtime > watcher['response_mtime']:
                    watcher['response_mtime'] = mtime
                    content = response_path.read_text(encoding='utf-8', errors='replace')
                    self._update_text_widget(watcher['response_text'], content)
            except Exception as e:
                print(f"Error reading response file: {e}")
    
    def _update_text_widget(self, text_widget: scrolledtext.ScrolledText, content: str):
        """Update a text widget with new content"""
        text_widget.configure(state=tk.NORMAL)
        
        # Save current position
        current_pos = text_widget.yview()
        at_bottom = current_pos[1] >= 0.99
        
        # Update content
        text_widget.delete(1.0, tk.END)
        text_widget.insert(1.0, content)
        
        # Restore position or scroll to bottom
        if at_bottom:
            text_widget.see(tk.END)
        else:
            text_widget.yview_moveto(current_pos[0])
        
        text_widget.configure(state=tk.DISABLED)
    
    def _process_log_updates(self):
        """Periodically check for log file updates"""
        try:
            # Only update if we're viewing a log view
            if self.current_view in self.log_watchers:
                self._update_log_view(self.current_view)
        except Exception as e:
            print(f"Error processing log updates: {e}")
        finally:
            # Schedule next update
            self.root.after(500, self._process_log_updates)  # Update every 500ms
    
    def _setup_narration_tags(self, widget):
        """Setup text tags for a widget"""
        widget.tag_configure("red", foreground="#ff6b6b")
        widget.tag_configure("green", foreground="#51cf66")
        widget.tag_configure("yellow", foreground="#ffd93d")
        widget.tag_configure("blue", foreground="#6bcfff")
        widget.tag_configure("cyan", foreground="#4ecdc4")
        widget.tag_configure("magenta", foreground="#ff6b9d")
        widget.tag_configure("bold", font=("Consolas", 11, "bold"))
        widget.tag_configure("dim", foreground="#888888")
        widget.tag_configure("bold_green", foreground="#51cf66", font=("Consolas", 11, "bold"))
        widget.tag_configure("bold_cyan", foreground="#4ecdc4", font=("Consolas", 11, "bold"))
        widget.tag_configure("quote", foreground="#87ceeb")
        widget.tag_configure("character", foreground="#daa520")
        widget.tag_configure("angle_left", foreground="#ffa500")
        widget.tag_configure("angle_right", foreground="#51cf66")
    
    def _show_sidebar_menu(self, event):
        """Show sidebar context menu"""
        # Check if click is on empty space (not on a widget)
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
        if widget == self.chapter_canvas or widget == self.chapter_list_frame:
            self.sidebar_menu.post(event.x_root, event.y_root)
    
    def _create_new_chapter(self):
        """Create a new chapter"""
        if self.chapter_manager:
            chapter = self.chapter_manager.create_chapter()
            self._refresh_chapter_list()
    
    def _refresh_chapter_list(self):
        """Refresh the chapter list display"""
        if not self.chapter_manager:
            return
        
        current_chapters = self.chapter_manager.get_all_chapters()
        
        # Check if we need a full refresh (compare chapter count and IDs)
        current_chapter_ids = set(chapter.id for chapter in current_chapters)
        existing_chapter_ids = set(self.chapter_widgets.keys())
        
        if current_chapter_ids == existing_chapter_ids:
            # Just update existing widgets
            for chapter in current_chapters:
                if chapter.id in self.chapter_widgets:
                    self.chapter_widgets[chapter.id].chapter = chapter
            return
        
        # Clear existing widgets only if necessary
        for widget in self.chapter_widgets.values():
            widget.destroy()
        self.chapter_widgets.clear()
        self.part_input_widgets.clear()
        
        # Create widgets for each chapter
        for chapter in current_chapters:
            chapter_widget = ChapterWidget(
                self.chapter_list_frame,
                chapter,
                self._on_chapter_select,
                self._on_chapter_delete,
                self._on_chapter_generate,
                self._on_part_input_change,
                self._on_part_generate,
                bg_color=self.bg_color,
                fg_color=self.fg_color,
                input_bg=self.input_bg
            )
            chapter_widget.pack(fill=tk.X, pady=5, padx=5)
            self.chapter_widgets[chapter.id] = chapter_widget
            
            # Bind mouse wheel events to the new chapter widget
            if hasattr(self, 'bind_mousewheel_to_widget'):
                self.bind_mousewheel_to_widget(chapter_widget)
    
    def _on_chapter_select(self, chapter_id: str):
        """Handle chapter selection"""
        self.current_chapter_id = chapter_id
        self._update_tabs_visibility()
        self._update_chapter_edit_tab()
        self._update_narration_log_tab()
    
    def _on_chapter_delete(self, chapter_id: str):
        """Handle chapter deletion"""
        if self.chapter_manager:
            self.chapter_manager.delete_chapter(chapter_id)
            if self.current_chapter_id == chapter_id:
                self.current_chapter_id = None
                self._update_tabs_visibility()
                self._clear_chapter_edit_tab()
                self._clear_narration_log_tab()
    
    def _on_chapter_generate(self, chapter_id: str):
        """Handle chapter generation request"""
        # This will be connected to the game engine
        if hasattr(self, 'generate_chapter_callback'):
            # Schedule the async coroutine to run in the event loop
            if hasattr(self, 'loop') and self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.generate_chapter_callback(chapter_id), 
                    self.loop
                )
            else:
                # Fallback for when event loop is not set
                print("Warning: No event loop set for async operations")
                return
    
    def _on_part_input_change(self, chapter_id: str, part_id: str, text: str):
        """Handle part input change"""
        if self.chapter_manager:
            self.chapter_manager.update_part(chapter_id, part_id, user_input=text)
    
    def _on_part_generate(self, chapter_id: str, part_id: str):
        """Handle single part generation request"""
        if hasattr(self, 'generate_part_callback'):
            # Schedule the async coroutine to run in the event loop
            if hasattr(self, 'loop') and self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.generate_part_callback(chapter_id, part_id), 
                    self.loop
                )
            else:
                # Fallback for when event loop is not set
                print("Warning: No event loop set for async operations")
                return
    
    def _on_chapter_data_change(self, event):
        """Handle changes to chapter data fields"""
        if not self.current_chapter_id or not self.chapter_manager:
            return
        
        # Get current values
        opening_summary = self.opening_summary_text.get("1.0", tk.END).strip()
        places = self.places_text.get("1.0", tk.END).strip()
        facts = self.facts_text.get("1.0", tk.END).strip()
        vocabulary = self.vocabulary_text.get("1.0", tk.END).strip()
        
        # Update chapter
        self.chapter_manager.update_chapter(
            self.current_chapter_id,
            opening_summary=opening_summary,
            places=places,
            facts=facts,
            vocabulary_guidance=vocabulary
        )
    
    def _update_chapter_edit_tab(self):
        """Update the chapter edit tab with current chapter data"""
        if not self.current_chapter_id or not self.chapter_manager:
            self._clear_chapter_edit_tab()
            return
        
        chapter = self.chapter_manager.get_chapter(self.current_chapter_id)
        if not chapter:
            self._clear_chapter_edit_tab()
            return
        
        # Update text widgets
        self.opening_summary_text.delete("1.0", tk.END)
        self.opening_summary_text.insert("1.0", chapter.opening_summary)
        
        self.places_text.delete("1.0", tk.END)
        self.places_text.insert("1.0", chapter.places)
        
        self.facts_text.delete("1.0", tk.END)
        self.facts_text.insert("1.0", chapter.facts)
        
        self.vocabulary_text.delete("1.0", tk.END)
        self.vocabulary_text.insert("1.0", chapter.vocabulary_guidance)
    
    def _clear_chapter_edit_tab(self):
        """Clear the chapter edit tab"""
        self.opening_summary_text.delete("1.0", tk.END)
        self.places_text.delete("1.0", tk.END)
        self.facts_text.delete("1.0", tk.END)
        self.vocabulary_text.delete("1.0", tk.END)
    
    def _update_narration_log_tab(self):
        """Update the narration log tab with all part narrations"""
        if not self.current_chapter_id or not self.chapter_manager:
            self._clear_narration_log_tab()
            return
        
        chapter = self.chapter_manager.get_chapter(self.current_chapter_id)
        if not chapter:
            self._clear_narration_log_tab()
            return
        
        # Clear and update
        self.combined_narration_log.configure(state=tk.NORMAL)
        self.combined_narration_log.delete("1.0", tk.END)
        
        # Add each part's narration
        for part in chapter.parts:
            if part.narration_log:
                self.combined_narration_log.insert(tk.END, f"\n[bold]Part {part.number}[/bold]\n")
                self.combined_narration_log.insert(tk.END, "-" * 50 + "\n")
                self._write_formatted_text_to_widget(
                    self.combined_narration_log, 
                    part.narration_log + "\n\n",
                    is_narrative=True
                )
        
        self.combined_narration_log.configure(state=tk.DISABLED)
    
    def _clear_narration_log_tab(self):
        """Clear the narration log tab"""
        self.combined_narration_log.configure(state=tk.NORMAL)
        self.combined_narration_log.delete("1.0", tk.END)
        self.combined_narration_log.configure(state=tk.DISABLED)
    
    def _update_tabs_visibility(self):
        """Show or hide the tabs container based on chapter selection"""
        if self.current_chapter_id:
            # Show tabs
            self.content_notebook.pack(fill=tk.BOTH, expand=True)
        else:
            # Hide tabs
            self.content_notebook.pack_forget()
    
    def populate_card_menu(self, cards: List[str], on_card_select: Callable):
        """Populate the card menu with available cards"""
        # Clear existing menu items
        self.card_menu.delete(0, tk.END)
        
        # Add card options
        for card in cards:
            self.card_menu.add_command(
                label=card,
                command=lambda c=card: on_card_select(c)
            )
    
    def _write_formatted_text_to_widget(self, widget, text, is_narrative=False):
        """Write formatted text to a specific widget"""
        # Similar to _write_formatted_text but for a specific widget
        tag_map = {
            '[red]': ('red', True),
            '[/red]': ('red', False),
            '[green]': ('green', True),
            '[/green]': ('green', False),
            '[yellow]': ('yellow', True),
            '[/yellow]': ('yellow', False),
            '[blue]': ('blue', True),
            '[/blue]': ('blue', False),
            '[cyan]': ('cyan', True),
            '[/cyan]': ('cyan', False),
            '[magenta]': ('magenta', True),
            '[/magenta]': ('magenta', False),
            '[bold]': ('bold', True),
            '[/bold]': ('bold', False),
            '[dim]': ('dim', True),
            '[/dim]': ('dim', False),
            '[bold green]': ('bold_green', True),
            '[/bold green]': ('bold_green', False),
            '[bold cyan]': ('bold_cyan', True),
            '[/bold cyan]': ('bold_cyan', False),
        }
        
        i = 0
        current_tags = []
        in_quotes = False
        
        while i < len(text):
            # Check for formatting tags
            tag_found = False
            for tag_text, (tag_name, is_start) in tag_map.items():
                if text[i:].startswith(tag_text):
                    if is_start:
                        if tag_name not in current_tags:
                            current_tags.append(tag_name)
                    else:
                        if tag_name in current_tags:
                            current_tags.remove(tag_name)
                    i += len(tag_text)
                    tag_found = True
                    break
            
            if tag_found:
                continue
            
            # Handle narrative-specific formatting
            if is_narrative:
                # Character names in [{name}]
                if text[i:i+2] == '[{' and '}]' in text[i:]:
                    end_idx = text.find('}]', i)
                    if end_idx != -1:
                        char_text = text[i:end_idx + 2]
                        widget.insert(tk.END, char_text, 'character')
                        i = end_idx + 2
                        continue
                
                # Quotes
                elif text[i] == '"':
                    if in_quotes:
                        widget.insert(tk.END, text[i])
                        in_quotes = False
                    else:
                        in_quotes = True
                        widget.insert(tk.END, text[i], 'quote')
                    i += 1
                    continue
                
                # Angle brackets
                elif text[i] == '<':
                    widget.insert(tk.END, text[i], 'angle_left')
                    i += 1
                    continue
                elif text[i] == '>':
                    widget.insert(tk.END, text[i], 'angle_right')
                    i += 1
                    continue
            
            # Regular character with current tags
            tags_to_apply = list(current_tags)
            if is_narrative and in_quotes:
                tags_to_apply.append('quote')
            
            if tags_to_apply:
                widget.insert(tk.END, text[i], tuple(tags_to_apply))
            else:
                widget.insert(tk.END, text[i])
            i += 1



class GUIOutputRedirect:
    """Redirect stdout to GUI"""
    def __init__(self, gui: GameEngineGUI, is_narrative: bool = False):
        self.gui = gui
        self.is_narrative = is_narrative
        
    def write(self, text: str):
        if text:
            self.gui.write(text, '', self.is_narrative)
            
    def flush(self):
        pass


class ChapterWidget(tk.Frame):
    """Widget for displaying and managing a chapter"""
    
    def __init__(self, parent, chapter: Chapter, 
                 on_select: Callable, on_delete: Callable, on_generate: Callable,
                 on_part_change: Callable, on_part_generate: Callable, **kwargs):
        bg_color = kwargs.pop('bg_color', '#1a1a1a')
        fg_color = kwargs.pop('fg_color', '#e0e0e0')
        input_bg = kwargs.pop('input_bg', '#2a2a2a')
        
        super().__init__(parent, bg=bg_color, **kwargs)
        
        self.chapter = chapter
        self.on_select = on_select
        self.on_delete = on_delete
        self.on_generate = on_generate
        self.on_part_change = on_part_change
        self.on_part_generate = on_part_generate
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.input_bg = input_bg
        self.is_expanded = True
        self.part_widgets: List[PartInputWidget] = []
        self._creating_new_part = False  # Flag to prevent multiple simultaneous creations
        
        self._create_widgets()
        
    def _create_widgets(self):
        # Chapter header
        header_frame = tk.Frame(self, bg=self.bg_color)
        header_frame.pack(fill=tk.X)
        
        # Expand/collapse button
        self.expand_btn = tk.Button(
            header_frame,
            text="▼" if self.is_expanded else "▶",
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Consolas", 10),
            bd=0,
            padx=5,
            command=self._toggle_expand
        )
        self.expand_btn.pack(side=tk.LEFT)
        
        # Chapter name (clickable)
        self.name_label = tk.Label(
            header_frame,
            text=self.chapter.name,
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Consolas", 11, "bold"),
            cursor="hand2"
        )
        self.name_label.pack(side=tk.LEFT, padx=5)
        self.name_label.bind("<Button-1>", lambda e: self.on_select(self.chapter.id))
        
        # Context menu
        self.context_menu = tk.Menu(self, tearoff=0, bg=self.input_bg, fg=self.fg_color)
        self.context_menu.add_command(label="Generate", command=self._on_generate)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete Chapter", command=self._on_delete)
        
        # Bind right-click
        self.bind("<Button-3>", self._show_context_menu)
        header_frame.bind("<Button-3>", self._show_context_menu)
        self.name_label.bind("<Button-3>", self._show_context_menu)
        
        # Parts container
        self.parts_frame = tk.Frame(self, bg=self.bg_color)
        if self.is_expanded:
            self.parts_frame.pack(fill=tk.X, padx=(20, 0))
        
        self._create_part_widgets()
    
    def _create_part_widgets(self):
        # Check if we need to recreate widgets (compare part count)
        if len(self.part_widgets) == len(self.chapter.parts):
            # Update existing widgets instead of recreating them
            for i, part in enumerate(self.chapter.parts):
                if i < len(self.part_widgets):
                    self.part_widgets[i].part = part
            return
        
        # Clear existing widgets only if necessary
        for widget in self.part_widgets:
            widget.destroy()
        self.part_widgets.clear()
        
        # Create widget for each part
        for part in self.chapter.parts:
            part_widget = PartInputWidget(
                self.parts_frame,
                part,
                self.on_part_change,
                self._check_create_new_part,
                self.on_part_generate,
                bg_color=self.bg_color,
                fg_color=self.fg_color,
                input_bg=self.input_bg
            )
            part_widget.pack(fill=tk.X, pady=2)
            self.part_widgets.append(part_widget)
            
            # Bind mouse wheel events to the part widget
            # Find the GUI instance through the widget hierarchy
            gui_widget = self
            while gui_widget and not hasattr(gui_widget, 'bind_mousewheel_to_widget'):
                gui_widget = gui_widget.master
            if gui_widget and hasattr(gui_widget, 'bind_mousewheel_to_widget'):
                gui_widget.bind_mousewheel_to_widget(part_widget)
    
    def _toggle_expand(self):
        self.is_expanded = not self.is_expanded
        self.expand_btn.config(text="▼" if self.is_expanded else "▶")
        
        if self.is_expanded:
            self.parts_frame.pack(fill=tk.X, padx=(20, 0))
        else:
            self.parts_frame.pack_forget()
    
    def _show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)
    
    def _on_generate(self):
        self.on_generate(self.chapter.id)
    
    def _on_delete(self):
        self.on_delete(self.chapter.id)
    
    def _check_create_new_part(self, part_widget: 'PartInputWidget'):
        """Check if we need to create a new part input"""
        # Prevent multiple simultaneous creations
        if self._creating_new_part:
            return
            
        # Check if widget and its parent still exist
        try:
            if not part_widget.winfo_exists() or not self.parts_frame.winfo_exists():
                return
        except tk.TclError:
            return
            
        # If this is the last part and it has text, create a new one
        if (self.part_widgets and 
            part_widget == self.part_widgets[-1] and 
            part_widget.part.user_input.strip()):
            # Set flag to prevent multiple creations
            self._creating_new_part = True
            
            try:
                # Add new part to chapter
                if hasattr(self, 'chapter') and hasattr(self.chapter, 'add_part'):
                    new_part = self.chapter.add_part()
                    # Create widget for new part - verify parent still exists
                    if self.parts_frame.winfo_exists():
                        new_widget = PartInputWidget(
                            self.parts_frame,
                            new_part,
                            self.on_part_change,
                            self._check_create_new_part,
                            self.on_part_generate,
                            bg_color=self.bg_color,
                            fg_color=self.fg_color,
                            input_bg=self.input_bg
                        )
                        new_widget.pack(fill=tk.X, pady=2)
                        self.part_widgets.append(new_widget)
                        
                        # Bind mouse wheel events to the new part widget
                        # Find the GUI instance through the widget hierarchy
                        gui_widget = self
                        while gui_widget and not hasattr(gui_widget, 'bind_mousewheel_to_widget'):
                            gui_widget = gui_widget.master
                        if gui_widget and hasattr(gui_widget, 'bind_mousewheel_to_widget'):
                            gui_widget.bind_mousewheel_to_widget(new_widget)
            except tk.TclError as e:
                print(f"Error creating new part widget: {e}")
            finally:
                # Reset flag after a short delay
                self.after(100, lambda: setattr(self, '_creating_new_part', False))
    
    def set_generating(self, is_generating: bool):
        """Set visual state for generation"""
        if is_generating:
            self.configure(bg="#3a4a5a")  # Light blue
        else:
            self.configure(bg=self.bg_color)
    
    def set_part_generating(self, part_id: str, is_generating: bool):
        """Set visual state for a specific part"""
        for widget in self.part_widgets:
            if widget.part.id == part_id:
                widget.set_generating(is_generating)
                break


class PartInputWidget(tk.Frame):
    """Widget for a single part input"""
    
    def __init__(self, parent, part: Part, on_change: Callable, 
                 on_text_change: Callable, on_part_generate: Callable, **kwargs):
        bg_color = kwargs.pop('bg_color', '#1a1a1a')
        fg_color = kwargs.pop('fg_color', '#e0e0e0')
        input_bg = kwargs.pop('input_bg', '#2a2a2a')
        
        super().__init__(parent, bg=bg_color, **kwargs)
        
        self.part = part
        self.on_change = on_change
        self.on_text_change = on_text_change
        self.on_part_generate = on_part_generate
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.input_bg = input_bg
        self._last_check_text = ""  # Track last text that triggered new part check
        self._check_timer = None  # Timer for debouncing new part checks
        
        self._create_widgets()
    
    def _create_widgets(self):
        # Part number label
        self.number_label = tk.Label(
            self,
            text=f"part_{self.part.number}_input",
            bg=self.bg_color,
            fg="#888888",
            font=("Consolas", 9)
        )
        self.number_label.pack(side=tk.LEFT, padx=(0, 5))
        
        # Input entry
        self.input_entry = tk.Entry(
            self,
            bg=self.input_bg,
            fg=self.fg_color,
            font=("Consolas", 10),
            insertbackground=self.fg_color,
            relief=tk.FLAT,
            bd=1
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.input_entry.insert(0, self.part.user_input)
        
        # Generate button (small)
        self.generate_btn = tk.Button(
            self,
            text="►",
            bg=self.input_bg,
            fg="#51cf66",
            font=("Consolas", 8, "bold"),
            width=2,
            height=1,
            relief=tk.FLAT,
            bd=1,
            command=self._on_generate
        )
        self.generate_btn.pack(side=tk.RIGHT)
        
        # Bind events
        self.input_entry.bind('<KeyRelease>', self._on_key_release)
        self.input_entry.bind('<FocusOut>', self._on_focus_out)
        self.input_entry.bind('<Tab>', self._on_tab)
    
    def _on_key_release(self, event):
        text = self.input_entry.get()
        # Only update if text actually changed
        if text != self.part.user_input:
            self.part.user_input = text
            self.on_change(self.part.chapter_id, self.part.id, text)
            
            # Debounce the new part check - only check after user stops typing
            # Cancel any existing timer
            if self._check_timer:
                self.after_cancel(self._check_timer)
                self._check_timer = None
            
            # Only schedule new part check if:
            # 1. Text has meaningful content
            # 2. Text is different from last check
            # 3. It's not just modifier keys
            if (text.strip() and 
                text != self._last_check_text and
                event.keysym not in ['Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R']):
                # Schedule check after 500ms of no typing
                self._check_timer = self.after(500, self._delayed_check_new_part)
    
    def _on_focus_out(self, event):
        # Cancel any pending check timer
        if self._check_timer:
            self.after_cancel(self._check_timer)
            self._check_timer = None
        
        # Save on focus loss
        text = self.input_entry.get()
        self.part.user_input = text
        self.on_change(self.part.chapter_id, self.part.id, text)
        
        # Check for new part when focus leaves, but be more careful
        if text.strip() and text != self._last_check_text:
            self._last_check_text = text
            # Use the delayed check method to avoid immediate widget creation during focus change
            self.after_idle(lambda: self._safe_text_change())
    
    def _on_tab(self, event):
        # Move to next widget
        event.widget.tk_focusNext().focus()
        return "break"
    
    def _delayed_check_new_part(self):
        """Called after debounce timeout to check if new part is needed"""
        self._check_timer = None
        try:
            text = self.input_entry.get()
            if text.strip() and text != self._last_check_text:
                self._last_check_text = text
                self.on_text_change(self)
        except tk.TclError:
            # Widget has been destroyed, ignore
            pass
    
    def _safe_text_change(self):
        """Safe wrapper for text change callback"""
        try:
            if self.winfo_exists():
                self.on_text_change(self)
        except tk.TclError:
            # Widget has been destroyed, ignore
            pass
    
    def _on_generate(self):
        """Handle generate button click"""
        if self.part.user_input.strip():  # Only generate if part has input
            self.on_part_generate(self.part.chapter_id, self.part.id)
    
    def set_generating(self, is_generating: bool):
        """Set visual state for generation"""
        if is_generating:
            self.input_entry.config(bg="#4a5a6a")  # Lighter blue
            self.generate_btn.config(text="⏸", fg="#ffd93d", state=tk.DISABLED)  # Pause symbol
        else:
            self.input_entry.config(bg=self.input_bg)
            self.generate_btn.config(text="►", fg="#51cf66", state=tk.NORMAL)  # Play symbol
    
    def destroy(self):
        """Clean up timers before destroying widget"""
        if self._check_timer:
            self.after_cancel(self._check_timer)
            self._check_timer = None
        super().destroy()