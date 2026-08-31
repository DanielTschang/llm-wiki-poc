# Use an agentic tool-calling loop for wiki edits, not fixed orchestration

Ingest, Query, and Lint all give the LLM `list_files`/`read_file`/`write_file` tools (scoped to `wiki/`) and let it decide which Wiki Pages to read and write across a multi-turn loop, rather than the script stuffing the whole wiki into one prompt and parsing a structured `{filename: content}` response back. The alternative is simpler to implement and easier to debug, but a single fixed-shape response doesn't scale to the doc's description of a single Ingest touching 10-15 pages, and doesn't match the doc's framing that "the LLM owns this layer entirely." Chosen for architectural fidelity to the pattern being prototyped, at the cost of more moving parts (tool loop, iteration cap, path-scoping enforcement) for what is otherwise a small POC.

## Considered Options

- **Fixed orchestration**: one prompt with full wiki + source content in, one structured JSON response out, script writes the files. Rejected as the default because it caps how many pages a single Operation can plausibly touch and diverges from the doc's "LLM owns this layer" framing — but noted as the fallback if the tool-calling loop proves unreliable in practice.
