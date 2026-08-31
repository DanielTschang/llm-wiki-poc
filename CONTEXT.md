# LLM Wiki POC

A Python3 proof-of-concept of the "LLM Wiki" pattern (see `doc/llm-index.md`): an LLM incrementally builds and maintains a persistent, cross-referenced markdown wiki from a collection of raw sources, instead of re-deriving answers from scratch on every query.

## Language

**Source**:
An immutable raw document in `raw/`. The LLM reads sources but never writes to `raw/` — sources are the fixed input to Ingest, never a tool-calling target.
_Avoid_: Document, file (when a Source specifically is meant)

**Wiki**:
The full maintained artifact living in `wiki/` — the set of all Wiki Pages plus the Index, the Log, and the Schema. What the doc calls "the wiki" as a whole. Stored on disk as an OKF v0.2 Knowledge Bundle (see `doc/okf-spec.md`).

**Wiki Page**:
A single LLM-generated content page in `wiki/` — a summary, entity page, concept page, or comparison. Produced either by Ingest (from a Source) or by Filing (from an Answer). Does *not* include the Index, Log, or Schema — those are distinct, special-purpose files even though they live in the same directory. Stored on disk as an OKF Concept document (YAML frontmatter with a required `type`, then a markdown body).
_Avoid_: Page, file, entry (when a Wiki Page specifically is meant)

**Index**:
`wiki/index.md`. The single content-oriented catalog of every Wiki Page (link + one-line summary), organized by category. Updated by the LLM whenever a Wiki Page is created or changed.

**Log**:
`wiki/log.md`. The append-only, chronological record of Operations. In this POC, entries are appended deterministically by the script (not the LLM) after each Operation completes, in a fixed `## [date] optype | title` format.

**Log Entry**:
A single line/section appended to the Log recording that one Operation happened. Every Operation (Ingest, Query, Lint) produces exactly one Log Entry, regardless of whether that Operation also produced a Wiki Page.

**Schema**:
`wiki/schema.md`. The POC's stand-in for the doc's CLAUDE.md/AGENTS.md concept — a conventions document (page types, index/log format, cross-link style) loaded into the LLM's system prompt on every Operation. Configuration for how the LLM behaves, not wiki content itself.

**Operation**:
One LLM-driven session triggered by a REPL command: an Ingest, a Query, or a Lint. Every Operation produces exactly one Log Entry; only Ingest and Filing can produce a Wiki Page.
_Avoid_: Op, action, command (when the triggered Operation itself is meant, as opposed to the REPL command syntax)

**Ingest**:
The Operation that processes one Source into wiki updates. The script reads the Source and hands its content to the LLM directly (the LLM never tool-calls into `raw/`); the LLM then explores and writes `wiki/` via tools, producing/updating one or more Wiki Pages and the Index.

**Query**:
The Operation that answers a question against the current wiki. Read-only over `wiki/` (the LLM may `list_files`/`read_file` but has no `write_file` tool during Query itself) and produces an Answer.

**Answer**:
The synthesized, cited response a Query produces. Ephemeral until Filed — printed to the console, not persisted, unless the user confirms Filing.

**Filing**:
The Operation, offered after every Query, that turns an Answer into a new Wiki Page. Distinct from Ingest: Filing's input is an Answer (something the wiki itself produced), not a Source (something external). Requires user confirmation; if confirmed, produces a Wiki Page, an Index update, and its own Log Entry.

**Lint**:
The read-only Operation that health-checks the wiki (contradictions, orphan pages, missing cross-references, stale claims) and produces a Lint Report. The LLM has no `write_file` tool during Lint — Lint can never produce or modify a Wiki Page.

**Lint Report**:
The output of a Lint Operation — printed to the console only. Not persisted as a Wiki Page; only the fact that the Lint ran is captured, via a Log Entry.
