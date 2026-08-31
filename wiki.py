#!/usr/bin/env python3
"""LLM Wiki POC — see doc/llm-index.md and CONTEXT.md for the pattern and terminology."""

import datetime
import json
import os
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("Missing dependency: run `pip install -r requirements.txt` first.", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("Missing dependency: run `pip install -r requirements.txt` first.", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("Missing dependency: run `pip install -r requirements.txt` first.", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
RAW_DIR = ROOT / "raw"
WIKI_DIR = ROOT / "wiki"
INDEX_PATH = WIKI_DIR / "index.md"
LOG_PATH = WIKI_DIR / "log.md"
SCHEMA_PATH = WIKI_DIR / "schema.md"

# wiki/ is an OKF v0.2 Knowledge Bundle. Every file except these two reserved
# names is an OKF Concept document and must carry frontmatter with a `type`.
RESERVED_FILENAMES = {"index.md", "log.md"}


# All three are overridable from .env / the environment, so pointing this at
# any OpenAI-compatible endpoint (DeepSeek, etc.) is a config change, not a
# code change.
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
BASE_URL = os.environ.get("OPENAI_BASE_URL")  # None => OpenAI SDK's default endpoint
ACTOR = f"openai/{MODEL}"  # OKF actor convention (§7): <producer>/<version>
MAX_TOOL_ITERATIONS = 15


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set. Put it in .env before running wiki.py.", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=api_key, base_url=BASE_URL)


# ---- Tools: path-scoped to wiki/ only. The LLM never gets a tool that can touch raw/. ----

def _resolve_wiki_path(rel_path: str) -> Path:
    wiki_root = WIKI_DIR.resolve()
    candidate = (WIKI_DIR / rel_path).resolve()
    if candidate != wiki_root and wiki_root not in candidate.parents:
        raise ValueError(f"path escapes wiki/: {rel_path}")
    return candidate


def tool_list_files() -> str:
    names = sorted(p.name for p in WIKI_DIR.glob("*.md"))
    return json.dumps(names)


def tool_read_file(path: str) -> str:
    try:
        target = _resolve_wiki_path(path)
    except ValueError as e:
        return f"ERROR: {e}"
    if not target.is_file():
        return f"ERROR: no such file: {path}"
    return target.read_text()


def _split_frontmatter(content: str) -> tuple[str, str] | None:
    """Split '---\\nYAML\\n---\\nbody' into (yaml_text, body). None if not OKF-shaped."""
    if not content.startswith("---"):
        return None
    lines = content.split("\n")
    if lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None


def _stamp_frontmatter(content: str) -> tuple[str | None, str]:
    """Validate OKF conformance (parseable YAML + non-empty `type`) and force-set
    `generated`. Returns (new_content, error) — exactly one is None."""
    split = _split_frontmatter(content)
    if split is None:
        return None, (
            "missing YAML frontmatter block. Every wiki page must start with a "
            "'---' delimited frontmatter block containing at least a 'type' field "
            "(see wiki/schema.md)."
        )
    fm_text, body = split
    try:
        frontmatter = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        return None, f"invalid YAML frontmatter: {e}"
    if not isinstance(frontmatter, dict) or not frontmatter.get("type"):
        return None, "frontmatter must include a non-empty 'type' field (see wiki/schema.md)."

    frontmatter["generated"] = {
        "by": ACTOR,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    new_fm_text = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{new_fm_text}\n---{body}", None


def tool_write_file(path: str, content: str) -> str:
    try:
        target = _resolve_wiki_path(path)
    except ValueError as e:
        return f"ERROR: {e}"
    if target.name in RESERVED_FILENAMES and target.name != "index.md":
        return f"ERROR: {target.name} is maintained by the script, not writable by tools."

    if target.name == "index.md":
        final_content = content
    else:
        final_content, error = _stamp_frontmatter(content)
        if error:
            return f"ERROR: {error}"

    try:
        target.write_text(final_content)
    except OSError as e:
        return f"ERROR: could not write {path}: {e}"
    return f"OK: wrote {path} ({len(final_content)} bytes)"


TOOL_IMPLS = {
    "list_files": lambda args: tool_list_files(),
    "read_file": lambda args: tool_read_file(args["path"]),
    "write_file": lambda args: tool_write_file(args["path"], args["content"]),
}

TOOL_SCHEMAS = {
    "list_files": {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List every filename currently in wiki/ (Wiki Pages plus index.md, log.md, schema.md).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a file in wiki/ by filename.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filename within wiki/, e.g. index.md or entity-fernweh-robotics.md",
                    }
                },
                "required": ["path"],
            },
        },
    },
    "write_file": {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create or overwrite a file in wiki/ with new content. Cannot write to log.md. "
                "Every file other than index.md must start with a '---' YAML frontmatter block "
                "containing a non-empty 'type' field (OKF v0.2) or the write is rejected — see "
                "wiki/schema.md for the type values this bundle uses."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Filename within wiki/ to write."},
                    "content": {"type": "string", "description": "Full new contents of the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
}


def run_tool_loop(client: OpenAI, system_prompt: str, user_message: str, allowed_tools) -> str:
    """Drive one Operation's agentic tool-calling loop to completion and return the LLM's final text."""
    tools = [TOOL_SCHEMAS[name] for name in allowed_tools]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            return message.content or ""
        for call in message.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if name not in TOOL_IMPLS or name not in allowed_tools:
                result = f"ERROR: tool not available in this Operation: {name}"
            else:
                result = TOOL_IMPLS[name](args)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    return "(stopped after reaching the max tool-call iteration limit without a final answer)"


def build_system_prompt(role_instructions: str) -> str:
    schema = SCHEMA_PATH.read_text()
    return (
        "You are the maintainer of a personal knowledge wiki, following the schema below.\n\n"
        f"{role_instructions}\n\n"
        "=== wiki/schema.md ===\n"
        f"{schema}"
    )


def append_log_entry(optype: str, title: str, detail: str = "") -> None:
    """Insert one bullet under today's OKF-style (§9) date heading, newest-first.

    log.md is a flat, date-grouped list ordered newest-first, e.g.:
        ## 2026-06-11
        - **Ingest**: 04-easa-regulation.md — ...
        ## 2026-06-10
        - **Query**: ...
    """
    date_heading = f"## {datetime.date.today().isoformat()}"
    bold = optype.capitalize()
    detail_line = detail.strip().replace("\n", " ")
    bullet = f"- **{bold}**: {title}" + (f" — {detail_line}" if detail_line else "")

    lines = LOG_PATH.read_text().splitlines(keepends=True)
    first_heading_idx = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    preamble, entries = lines[:first_heading_idx], lines[first_heading_idx:]

    if entries and entries[0].rstrip("\n") == date_heading:
        insert_at = 1
        while insert_at < len(entries) and entries[insert_at].strip() == "":
            insert_at += 1
        entries[insert_at:insert_at] = [bullet + "\n"]
    else:
        if preamble and preamble[-1].strip() != "":
            preamble.append("\n")
        entries[0:0] = [date_heading + "\n", "\n", bullet + "\n", "\n"]

    LOG_PATH.write_text("".join(preamble) + "".join(entries))


def resolve_source_path(path_arg: str) -> Path | None:
    source_path = Path(path_arg)
    if not source_path.is_absolute():
        candidate = RAW_DIR / path_arg
        if candidate.is_file():
            source_path = candidate
    return source_path if source_path.is_file() else None


def cmd_ingest(client: OpenAI, path_arg: str) -> None:
    source_path = resolve_source_path(path_arg)
    if source_path is None:
        print(f"No such source file: {path_arg}")
        return

    source_text = source_path.read_text()
    system_prompt = build_system_prompt(
        "This is an Ingest Operation. You will be given the full text of one new Source. "
        "Use list_files and read_file to see the current state of the wiki, then use write_file "
        "to create or update whichever Entity and Topic pages are affected, create exactly one "
        "Source Summary page for this source, and update index.md. Record provenance with a "
        "'sources' frontmatter entry pointing at this source (see wiki/schema.md). "
        "When you are done writing, reply with a final short plain-text message (no tool call) "
        "summarizing which pages you created or updated."
    )
    user_message = f"New source: {source_path.name}\n\n---\n{source_text}\n---"
    print(f"Ingesting {source_path.name}...")
    result = run_tool_loop(client, system_prompt, user_message, ("list_files", "read_file", "write_file"))
    print(result)
    append_log_entry("ingest", source_path.name, result.strip())


def cmd_query(client: OpenAI, question: str) -> None:
    system_prompt = build_system_prompt(
        "This is a Query Operation. Use list_files and read_file to explore the wiki — start with "
        "index.md — then answer the user's question, citing which wiki pages you drew on by filename. "
        "You do not have write_file access during this Operation."
    )
    print("Thinking...")
    answer = run_tool_loop(client, system_prompt, question, ("list_files", "read_file"))
    print(f"\n{answer}\n")
    append_log_entry("query", question, answer.strip())

    choice = input("File this answer as a new wiki page? [y/N] ").strip().lower()
    if choice != "y":
        return

    file_system_prompt = build_system_prompt(
        "This is a Filing Operation, following a Query. You already produced an Answer for the "
        "user's question, included below along with the question itself. Write it as a new Filed "
        "Answer page (answer-<slug>.md, type: 'Filed Answer'), with a 'sources' frontmatter entry "
        "for each wiki page it drew on (resource: /<filename>.md), and update index.md under "
        "'Filed Answers'. Use list_files/read_file first if you need to confirm filenames. Reply "
        "with a final short plain-text message naming the file you created."
    )
    file_user_message = f"Question: {question}\n\nAnswer to file:\n{answer}"
    file_result = run_tool_loop(
        client, file_system_prompt, file_user_message, ("list_files", "read_file", "write_file")
    )
    print(file_result)
    append_log_entry("filing", question, file_result.strip())


def cmd_lint(client: OpenAI) -> None:
    system_prompt = build_system_prompt(
        "This is a Lint Operation. Use list_files and read_file to review the whole wiki for: "
        "contradictions between pages, stale claims superseded by newer sources, orphan pages with "
        "no inbound links, important concepts mentioned but lacking their own page, and missing "
        "cross-references. You do not have write_file access — report findings only, do not fix "
        "them. Reply with a final plain-text report."
    )
    print("Linting...")
    report = run_tool_loop(
        client, system_prompt, "Run a lint pass over the current wiki.", ("list_files", "read_file")
    )
    print(f"\n{report}\n")
    append_log_entry("lint", "wiki health check", report.strip())


INDEX_SCAFFOLD = """---
okf_version: "0.2"
---

# Index

Catalog of every Wiki Page. Updated on every Operation that adds or renames a page.

# Entities

_(none yet)_

# Topics

_(none yet)_

# Source Summaries

_(none yet)_

# Filed Answers

_(none yet)_
"""

LOG_SCAFFOLD = """# Wiki Update Log

Newest-first, one dated section per day. Maintained by the script, not the LLM.
"""

# Files reset never touches — the bundle's own configuration, not generated content.
RESET_KEEP = {"schema.md"}


def cmd_reset() -> None:
    """Delete every generated Wiki Page and restore index.md/log.md to their pristine
    scaffold, so /demo (or manual /ingest) can be re-run from a clean slate."""
    to_delete = sorted(
        p for p in WIKI_DIR.glob("*.md") if p.name not in RESET_KEEP | RESERVED_FILENAMES
    )
    if not to_delete and INDEX_PATH.read_text() == INDEX_SCAFFOLD and LOG_PATH.read_text() == LOG_SCAFFOLD:
        print("Wiki is already at its pristine scaffold state.")
        return

    print(f"This will delete {len(to_delete)} wiki page(s) and reset index.md/log.md:")
    for p in to_delete:
        print(f"  - {p.name}")
    choice = input("Continue? [y/N] ").strip().lower()
    if choice != "y":
        print("Reset cancelled.")
        return

    for p in to_delete:
        p.unlink()
    INDEX_PATH.write_text(INDEX_SCAFFOLD)
    LOG_PATH.write_text(LOG_SCAFFOLD)
    print("Wiki reset to its pristine scaffold state.")


DEMO_QUESTION = (
    "What's the relationship between Fernweh Robotics and Aerotote Systems, and how does the new "
    "EASA regulation affect each of them differently?"
)


def cmd_demo(client: OpenAI) -> None:
    sources = sorted(RAW_DIR.glob("*.md"))
    if not sources:
        print("No sources found in raw/.")
        return
    for source in sources:
        cmd_ingest(client, str(source))
        print()
    cmd_query(client, DEMO_QUESTION)
    print()
    cmd_lint(client)


HELP = """
Commands:
  /ingest <path>      Ingest a source (path relative to raw/, or absolute)
  /query <question>   Ask a question against the wiki
  /lint                Run a read-only wiki health check
  /demo                Ingest every source in raw/, run a sample query, then lint
  /reset               Delete generated wiki pages and reset index.md/log.md (for re-demoing)
  /help                Show this help
  /quit                Exit
""".strip()


def main() -> None:
    client = get_client()
    print("LLM Wiki POC — type /help for commands.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/quit", "/exit"):
            break
        if line == "/help":
            print(HELP)
        elif line == "/lint":
            cmd_lint(client)
        elif line == "/demo":
            cmd_demo(client)
        elif line == "/reset":
            cmd_reset()
        elif line.startswith("/ingest "):
            cmd_ingest(client, line[len("/ingest "):].strip())
        elif line.startswith("/query "):
            cmd_query(client, line[len("/query "):].strip())
        else:
            print(f"Unknown command: {line}. Type /help for commands.")


if __name__ == "__main__":
    main()
