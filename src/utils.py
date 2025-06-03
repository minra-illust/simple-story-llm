from openai import OpenAI
from colorama import Fore, Style, init
import json
import os
import threading
from functools import partial
import re
init()
def print_highlighted_text(text, end="\n"):
    highlighted_text = ""
    highlighted = False
    for char in text:
        if char == '"':
            highlighted_text += Fore.CYAN + char
            if highlighted:
                highlighted_text += Style.RESET_ALL
            highlighted = not highlighted
        elif char == '*':
            highlighted_text += Fore.MAGENTA + char
            if highlighted:
                highlighted_text += Style.RESET_ALL
            highlighted = not highlighted
        elif char == '[' or char == ']':
            highlighted_text += Fore.YELLOW + char
            if highlighted:
                highlighted_text += Style.RESET_ALL
            highlighted = not highlighted
        else:
            highlighted_text += char
    highlighted_text += Style.RESET_ALL
    print(highlighted_text, end=end)
def get_user_input(prompt="*Command:* "):
    print_highlighted_text(prompt, end='')
    first_line = ""
    try:
        first_line = input().strip()
    except:
        first_line = "bye"
    return first_line


def print_rich(text: str, end: str = "\n"):
    """Print text with rich formatting support for color tags."""
    # Simple color mapping
    color_map = {
        '[red]': Fore.RED,
        '[/red]': Style.RESET_ALL,
        '[green]': Fore.GREEN,
        '[/green]': Style.RESET_ALL,
        '[yellow]': Fore.YELLOW,
        '[/yellow]': Style.RESET_ALL,
        '[blue]': Fore.BLUE,
        '[/blue]': Style.RESET_ALL,
        '[cyan]': Fore.CYAN,
        '[/cyan]': Style.RESET_ALL,
        '[magenta]': Fore.MAGENTA,
        '[/magenta]': Style.RESET_ALL,
        '[bold]': Style.BRIGHT,
        '[/bold]': Style.RESET_ALL,
        '[dim]': Style.DIM,
        '[/dim]': Style.RESET_ALL,
        '[bold green]': Style.BRIGHT + Fore.GREEN,
        '[/bold green]': Style.RESET_ALL,
        '[bold cyan]': Style.BRIGHT + Fore.CYAN,
        '[/bold cyan]': Style.RESET_ALL,
    }
    
    formatted_text = text
    for tag, color in color_map.items():
        formatted_text = formatted_text.replace(tag, color)
    
    print(formatted_text + Style.RESET_ALL, end=end)


def print_section_header(title: str):
    """Print a formatted section header."""
    print()
    print_rich(f"[bold cyan]{'='*50}[/bold cyan]")
    print_rich(f"[bold cyan]{title.center(50)}[/bold cyan]")
    print_rich(f"[bold cyan]{'='*50}[/bold cyan]")
    print()


def print_narrative(text: str):
    """Print narrative text with custom color patterns for LLM output."""
    import re
    
    # First apply rich formatting tags
    formatted_text = text
    color_map = {
        '[red]': Fore.RED,
        '[/red]': Style.RESET_ALL,
        '[green]': Fore.GREEN,
        '[/green]': Style.RESET_ALL,
        '[yellow]': Fore.YELLOW,
        '[/yellow]': Style.RESET_ALL,
        '[blue]': Fore.BLUE,
        '[/blue]': Style.RESET_ALL,
        '[cyan]': Fore.CYAN,
        '[/cyan]': Style.RESET_ALL,
        '[magenta]': Fore.MAGENTA,
        '[/magenta]': Style.RESET_ALL,
        '[bold]': Style.BRIGHT,
        '[/bold]': Style.RESET_ALL,
        '[dim]': Style.DIM,
        '[/dim]': Style.RESET_ALL,
    }
    
    for tag, color in color_map.items():
        formatted_text = formatted_text.replace(tag, color)
    
    # Now apply custom patterns
    result = ""
    i = 0
    in_quotes = False
    
    while i < len(formatted_text):
        char = formatted_text[i]
        
        # Check for character names in square brackets [{character}]
        if char == '[' and i + 1 < len(formatted_text) and formatted_text[i + 1] == '{':
            # Find the closing }]
            end_idx = formatted_text.find('}]', i)
            if end_idx != -1:
                # Light brown color for character names
                result += Fore.YELLOW + Style.DIM + formatted_text[i:end_idx + 2] + Style.RESET_ALL
                i = end_idx + 2
                continue
        
        # Handle quotes
        elif char == '"':
            if in_quotes:
                # End of quoted text
                result += char + Style.RESET_ALL
                in_quotes = False
            else:
                # Start of quoted text - light blue
                result += Fore.CYAN + Style.BRIGHT + char
                in_quotes = True
            i += 1
            
        # Handle < and >
        elif char == '<':
            # Light orange (using yellow with dim style)
            result += Fore.YELLOW + Style.BRIGHT + char + Style.RESET_ALL
            i += 1
            
        elif char == '>':
            # Green
            result += Fore.GREEN + char + Style.RESET_ALL
            i += 1
            
        else:
            # Regular character
            if in_quotes:
                # Continue light blue for quoted text
                result += char
            else:
                result += char
            i += 1
    
    # Ensure we reset at the end
    print(result + Style.RESET_ALL)
