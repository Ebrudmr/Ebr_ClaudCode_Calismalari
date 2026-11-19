# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A small, dependency-free Python agent (stdlib only, Python 3.10+ — keep it that way; no `pip install`). It reads meeting notes from `notes/`, extracts action items and urgent tasks, and writes a Markdown report. User-facing text, CLI flags, tool names, and dict keys are in Turkish.

## Commands

```bash
python3 agent.py                          # read notes/, print log + report, write rapor.md
python3 agent.py --bugun 2026-11-19       # fix the reference date (urgency depends on "today")
python3 agent.py --notlar DIR --rapor OUT.md
```

There is no test suite, linter, or build step. To check a change, run the agent with a fixed `--bugun` date; the sample notes are dated around 2026-11-19, so that date exercises every case (overdue, due today, due soon, keyword-urgent, not urgent, plus a non-action warning). `rapor.md` is generated and gitignored.

## Architecture

- `tools.py` holds the tools as plain functions: `read_files(folder)` returns `{filename: text}` for `.txt`/`.md` files (empty dict if the folder is missing, so the agent can decide what to do), and `extract_actions(text, source, today)` returns `{"aksiyonlar", "acil_isler", "uyarilar"}`. Each action dict has the keys `gorev, sorumlu, son_tarih, toplanti, kaynak, acil, acil_nedenleri`; the report in `agent.py` depends on these names.
- `agent.py` registers tools by name in the `TOOLS` dict. `NotesAgent.run()` is a queue-driven loop: `plan()` seeds the first step (read files), and `observe()` inspects each tool result and returns the next steps (one `aksiyonlari_ayikla` step per file read) or `None` to stop. Then `decide()` builds the prioritization message and `report()` renders and writes the Markdown. To add a tool: add the function to `tools.py`, register it in `TOOLS`, and handle its result in a new branch of `observe()` (unknown tools raise).

## Note-parsing conventions (`tools.py`)

- A line is an action only if it starts (after an optional `-`/`*` bullet) with `[ ]`, `AKSİYON:`, `TODO:`, `Yapılacak:`, or `ACİL:`. Owner is the first `@name`; the deadline is the last date on the line (`dd.mm.yyyy` or `yyyy-mm-dd`).
- `#` header lines set the meeting date for the lines below them.
- An action is urgent if it contains a keyword in `URGENT_KEYWORDS`, or its deadline is past, today, or within `URGENT_WINDOW_DAYS`. Non-action lines that contain urgent keywords become `uyarilar` (warnings).
- Use `tr_lower()` rather than `str.lower()` before matching. Plain `.lower()` turns `İ` into two characters, which breaks keyword matching and the character offsets used to slice the original line.
