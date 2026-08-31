# LLM Wiki POC

A minimal Python3 proof-of-concept of the "LLM Wiki" pattern described in [`doc/llm-index.md`](doc/llm-index.md),
with `wiki/` stored as an [OKF v0.2](doc/okf-spec.md) Knowledge Bundle.
See [`CONTEXT.md`](CONTEXT.md) for the terminology (Source, Wiki Page, Index, Log, Schema, Ingest, Query, Filing, Lint),
[`docs/adr/0001-agentic-tool-calling-for-wiki-edits.md`](docs/adr/0001-agentic-tool-calling-for-wiki-edits.md) for why
the LLM edits the wiki via tool-calling rather than one structured response, and
[`docs/adr/0002-okf-as-wiki-storage-format.md`](docs/adr/0002-okf-as-wiki-storage-format.md) for the OKF adoption.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Put your key in `.env` (already git-ignored); `wiki.py` loads it automatically on startup
(`export OPENAI_API_KEY=...` also works and takes precedence):

```
OPENAI_API_KEY=sk-...
```

Defaults to OpenAI's `gpt-4o-mini` against the default endpoint. To point at any other
OpenAI-compatible provider instead — no code changes — set `OPENAI_BASE_URL` and
`OPENAI_MODEL` in `.env` too. For DeepSeek:

```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

## Run

```bash
python3 wiki.py
```

Inside the REPL:

```
/ingest 01-fernweh-launch.md   # path is relative to raw/, or absolute
/query What does Fernweh Robotics do?
/lint
/demo                           # ingests every source in raw/, runs a sample query, then lints
/help
/quit
```

`raw/` ships with four toy sources about a fictional drone-delivery startup (Fernweh Robotics) and
its rival (Aerotote Systems), including a later regulatory update that contradicts an earlier claim
— useful for seeing Ingest build cross-referenced pages and Lint catch the stale claim.

## Layout

```
raw/            immutable source documents (never written to by the LLM)
wiki/            an OKF v0.2 Knowledge Bundle
  index.md      catalog of every Wiki Page (OKF reserved filename, no frontmatter required)
  log.md        newest-first, date-grouped record of Operations (OKF §9, script-maintained)
  schema.md     wiki conventions, loaded into every Operation's system prompt (itself an OKF Concept)
  entity-*.md, topic-*.md, summary-*.md, answer-*.md   LLM-maintained Wiki Pages (OKF Concepts:
                                                        type Entity / Topic / Source Summary / Filed Answer)
wiki.py         the REPL; write_file rejects any Concept file missing valid OKF frontmatter
```
