"""Log helper functions"""

from rich.console import Console
from rich.prompt import Prompt
from rich.theme import Theme


theme = Theme(
    {
        "info": "blue",
        "okay": "green",
        "warn": "yellow",
        "error": "red",
        "hl": "bold",
    }
)

console = Console(theme=theme)


def prompt_yes_no(text):
    return Prompt.ask(text, choices=["y", "n"]) == "y"


def info(text, value=None):
    result = f"[info][info][/info] {text}"

    if value is not None:
        result += ": " + f"[hl]{value}[/hl]"

    console.log(result)


def okay(text, value=None):
    result = f"[okay][okay][/okay] {text}"

    if value is not None:
        result += ": " + f"[hl]{value}[/hl]"

    console.log(result)


def warn(text, value=None):
    result = f"[warn][warn][/warn] {text}"

    if value is not None:
        result += ": " + f"[hl]{value}[/hl]"

    console.log(result)


def error(text, value=None):
    result = f"[error][error][/error] {text}"

    if value is not None:
        result += ": " + f"[hl]{value}[/hl]"

    console.log(result)
