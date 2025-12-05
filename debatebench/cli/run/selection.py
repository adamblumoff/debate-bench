"""Interactive selection helpers for the `debatebench run` command."""
from __future__ import annotations

from typing import List

import typer
from rich.console import Console
from rich.table import Table


class SelectionCancelled(Exception):
    """Raised when the user cancels the selection wizard."""


def _interactive_select_models(catalog, console: Console, title: str = "OpenRouter Models (alphabetical)"):
    """
    Curses-based selector: arrow keys to move, Enter/Space to toggle, c to continue, q to cancel.
    Falls back to simple enable prompt if curses is unavailable.
    """
    try:
        import curses
    except Exception:
        return _fallback_select_models(catalog, console)

    def menu(stdscr):
        curses.curs_set(0)
        selected = [False] * len(catalog)
        idx = 0

        def draw():
            stdscr.clear()
            header = f"{title} (Enter/Space toggle ON/OFF, ↑/↓ move, c=continue, q=cancel; default is OFF)"
            stdscr.addstr(0, 0, header, curses.A_BOLD)
            max_rows = curses.LINES - 2
            start = max(0, idx - max_rows + 1)
            visible = catalog[start : start + max_rows]
            for offset, entry in enumerate(visible):
                real_idx = start + offset
                cursor = ">" if real_idx == idx else " "
                mark = "[x]" if selected[real_idx] else "[ ]"
                line = f"{cursor} {mark} {entry['id']} ({entry['created'].strftime('%Y-%m-%d')})"
                stdscr.addstr(offset + 1, 0, line[: curses.COLS - 1])
            stdscr.refresh()

        draw()
        while True:
            ch = stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % len(catalog)
            elif ch in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % len(catalog)
            elif ch in (10, 13, ord(" "), ord("\n")):  # Enter or space toggles
                selected[idx] = not selected[idx]
            elif ch in (ord("c"), ord("C")):  # continue
                return [c for i, c in enumerate(catalog) if selected[i]]
            elif ch in (ord("q"), ord("Q")):
                return []
            draw()

    try:
        return curses.wrapper(menu)
    except Exception:
        return _fallback_select_models(catalog, console)


def _fallback_select_models(catalog, console: Console, title: str = "OpenRouter Models (alphabetical)"):
    """
    Simpler prompt fallback: show table, accept comma-separated indexes to enable.
    """
    table = Table(title=title)
    table.add_column("#", justify="right")
    table.add_column("Model ID")
    table.add_column("Created (UTC)")
    for idx, entry in enumerate(catalog, start=1):
        table.add_row(str(idx), entry["id"], entry["created"].strftime("%Y-%m-%d"))
    console.print(table)

    prompt_text = "Enter comma-separated indexes to enable (blank enables none): "
    disable_raw = typer.prompt(prompt_text, default="")
    enabled: set[int] = set()
    if disable_raw.strip():
        parts = [p.strip() for p in disable_raw.split(",")]
        for p in parts:
            if not p:
                continue
            try:
                val = int(p)
            except ValueError:
                raise typer.BadParameter(f"Invalid index: {p}")
            if val < 1 or val > len(catalog):
                raise typer.BadParameter(f"Index out of range: {val}")
            enabled.add(val)

    return [e for idx, e in enumerate(catalog, start=1) if idx in enabled]


def _interactive_select_topics(topics, console: Console):
    """
    Topic selector shown before models. Defaults to OFF; user toggles ON.
    """
    try:
        import curses
    except Exception:
        return _fallback_select_topics(topics, console)

    topics_sorted = sorted(topics, key=lambda t: (t.category or "", t.motion))

    def menu(stdscr):
        curses.curs_set(0)
        selected = [False] * len(topics_sorted)
        idx = 0

        def draw():
            stdscr.clear()
            stdscr.addstr(
                0,
                0,
                "Topics (Enter/Space toggle ON/OFF, ↑/↓ move, c=continue, q=cancel; default is OFF)",
                curses.A_BOLD,
            )
            max_rows = curses.LINES - 2
            start = max(0, idx - max_rows + 1)
            visible = topics_sorted[start : start + max_rows]
            for offset, entry in enumerate(visible):
                real_idx = start + offset
                cursor = ">" if real_idx == idx else " "
                mark = "[x]" if selected[real_idx] else "[ ]"
                motion = entry.motion if len(entry.motion) < curses.COLS - 20 else entry.motion[: curses.COLS - 23] + "..."
                cat = entry.category or "-"
                line = f"{cursor} {mark} {cat}: {motion}"
                stdscr.addstr(offset + 1, 0, line[: curses.COLS - 1])
            stdscr.refresh()

        draw()
        while True:
            ch = stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % len(topics)
            elif ch in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % len(topics)
            elif ch in (10, 13, ord(" "), ord("\n")):  # Enter or space toggles
                selected[idx] = not selected[idx]
            elif ch in (ord("c"), ord("C")):  # continue
                return [t for i, t in enumerate(topics_sorted) if selected[i]]
            elif ch in (ord("q"), ord("Q")):
                return []
            draw()

    try:
        return curses.wrapper(menu)
    except Exception:
        return _fallback_select_topics(topics, console)


def _fallback_select_topics(topics, console: Console):
    table = Table(title="Topics")
    table.add_column("#", justify="right")
    table.add_column("Category")
    table.add_column("Motion")
    table.add_column("Category")
    topics_sorted = sorted(topics, key=lambda t: (t.category or "", t.motion))
    for idx, t in enumerate(topics_sorted, start=1):
        table.add_row(str(idx), t.category or "-", t.motion, t.category or "-")
    console.print(table)
    prompt_text = "Enter comma-separated indexes to ENABLE (blank enables none): "
    raw = typer.prompt(prompt_text, default="")
    enabled: set[int] = set()
    if raw.strip():
        parts = [p.strip() for p in raw.split(",")]
        for p in parts:
            if not p:
                continue
            try:
                val = int(p)
            except ValueError:
                raise typer.BadParameter(f"Invalid index: {p}")
            if val < 1 or val > len(topics_sorted):
                raise typer.BadParameter(f"Index out of range: {val}")
            enabled.add(val)
    return [t for idx, t in enumerate(topics_sorted, start=1) if idx in enabled]


def selection_wizard(
    topics,
    model_catalog,
    judge_catalog,
    enable_topics: bool,
    enable_models: bool,
    enable_judges: bool,
    popular_ids: List[str] | None = None,
):
    """
    Unified curses wizard for topic/model/judge selection.
    Returns (selected_topics, selected_models, selected_judges) or None if cancelled.
    """
    try:
        import curses
    except Exception:
        return None

    steps = []
    if enable_topics and topics:
        topics_sorted = sorted(topics, key=lambda t: (t.category or "", t.motion))
        steps.append(
            {
                "name": "Topics",
                "items": topics_sorted,
                "selected": [False] * len(topics_sorted),
                "type": "topic",
            }
        )
    if enable_models and model_catalog:
        steps.append(
            {
                "name": "Debaters",
                "items": model_catalog,
                "selected": [False] * len(model_catalog),
                "type": "model",
            }
        )
    if enable_judges and judge_catalog:
        steps.append(
            {
                "name": "Judges",
                "items": judge_catalog,
                "selected": [False] * len(judge_catalog),
                "type": "judge",
            }
        )

    if not steps:
        return None

    def render_line(stdscr, row, text, highlight=False):
        maxw = curses.COLS - 1
        txt = text[: maxw]
        if highlight:
            stdscr.addstr(row, 0, txt, curses.A_REVERSE)
        else:
            stdscr.addstr(row, 0, txt)

    def menu(stdscr):
        curses.curs_set(0)
        step_idx = 0
        cursor_idx = 0

        def clamp_cursor():
            nonlocal cursor_idx
            curr_items = steps[step_idx]["items"]
            if not curr_items:
                cursor_idx = 0
            else:
                cursor_idx = max(0, min(cursor_idx, len(curr_items) - 1))

        def draw():
            stdscr.clear()
            step = steps[step_idx]
            total_steps = len(steps)
            header = (
                f"Step {step_idx+1}/{total_steps} - {step['name']} "
                "(Space/Enter toggle, ↑/↓ move, n=next, b=back, q=cancel)"
            )
            render_line(stdscr, 0, header, highlight=True)
            items = step["items"]
            selected = step["selected"]
            max_rows = curses.LINES - 2
            start = max(0, cursor_idx - max_rows + 1)
            visible = items[start : start + max_rows]
            for offset, entry in enumerate(visible):
                real_idx = start + offset
                cursor = ">" if real_idx == cursor_idx else " "
                mark = "[x]" if selected[real_idx] else "[ ]"
                if step["type"] == "topic":
                    cat = entry.category or "-"
                    motion = entry.motion
                    desc = f"{cat}: {motion}"
                else:
                    created = entry.get("created")
                    cstr = created.strftime("%Y-%m-%d") if created else ""
                    desc = f"{entry.get('id')} ({cstr})"
                line = f"{cursor} {mark} {desc}"
                render_line(stdscr, offset + 1, line)
            stdscr.refresh()

        draw()
        while True:
            ch = stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                cursor_idx = max(0, cursor_idx - 1)
            elif ch in (curses.KEY_DOWN, ord("j")):
                cursor_idx = min(len(steps[step_idx]["items"]) - 1, cursor_idx + 1)
            elif ch in (10, 13, ord(" "), ord("\n")):
                if steps[step_idx]["items"]:
                    steps[step_idx]["selected"][cursor_idx] = not steps[step_idx]["selected"][cursor_idx]
            elif ch in (ord("n"), ord("N")):
                if step_idx < len(steps) - 1:
                    step_idx += 1
                    clamp_cursor()
                else:
                    break
            elif ch in (ord("b"), ord("B")):
                if step_idx > 0:
                    step_idx -= 1
                    clamp_cursor()
            elif ch in (ord("q"), ord("Q")):
                raise SelectionCancelled()
            draw()

        # Gather selections
        sel_topics = []
        sel_models = []
        sel_judges = []
        for st in steps:
            if st["type"] == "topic":
                sel_topics = [t for i, t in enumerate(st["items"]) if st["selected"][i]]
            elif st["type"] == "model":
                sel_models = [m for i, m in enumerate(st["items"]) if st["selected"][i]]
            elif st["type"] == "judge":
                sel_judges = [m for i, m in enumerate(st["items"]) if st["selected"][i]]
        return sel_topics, sel_models, sel_judges

    return curses.wrapper(menu)


__all__ = [
    "SelectionCancelled",
    "_interactive_select_models",
    "_fallback_select_models",
    "_interactive_select_topics",
    "_fallback_select_topics",
    "selection_wizard",
]
