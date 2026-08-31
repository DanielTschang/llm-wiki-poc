---
type: Schema Document
title: Wiki Schema
description: Conventions for maintaining this wiki as an OKF v0.2 Knowledge Bundle.
---

# Wiki Schema

This wiki (`wiki/`) is an [OKF](../doc/okf-spec.md) v0.2 **Knowledge Bundle**. Every file
in it except `index.md` and `log.md` is an OKF **Concept** document: YAML frontmatter,
then a markdown body. Read this before every Operation.

## Frontmatter is enforced by the tool, not just by convention

`write_file` rejects any non-reserved file (i.e. anything other than `index.md`/`log.md`)
that doesn't start with a `---`-delimited YAML frontmatter block containing a non-empty
`type`. You do not need to set `generated` yourself — the tool overwrites it on every
write with the correct actor and timestamp. Everything else in frontmatter is yours to set.

## Page types

Use one of these `type` values (OKF types are free-form strings, not centrally
registered — these four are this bundle's own convention):

| `type`            | Filename convention   | One per...                                   |
| ------------------ | ---------------------- | --------------------------------------------- |
| `Entity`           | `entity-<slug>.md`     | company, person, or product                   |
| `Topic`            | `topic-<slug>.md`      | recurring theme spanning multiple entities    |
| `Source Summary`   | `summary-<slug>.md`    | ingested Source, one page per Source          |
| `Filed Answer`     | `answer-<slug>.md`     | Query Answer the user chose to file           |

All pages are flat files directly in `wiki/` — no subdirectories.

## Frontmatter fields to use

- `type`: REQUIRED (see table above).
- `title`, `description`: RECOMMENDED — a display name and one-line summary.
- `tags`: optional list of short strings.
- `sources`: when a page derives from a Source or from other Wiki Pages, list them:
  ```yaml
  sources:
    - id: fernweh-launch
      resource: ../raw/01-fernweh-launch.md
      title: Fernweh Robotics Unveils "Sparrow" Delivery Drone
  ```
  Use a bundle-relative path (`../raw/<file>` for a Source, `/entity-foo.md` for another
  Wiki Page) as `resource`. Give each entry a short `id` and cite specific claims with a
  matching markdown footnote, e.g. `Sparrow carries 2.5kg payloads.[^fernweh-launch]`.
- `status`: `draft | stable | deprecated`, only if a page needs to say it's not current.

Do not set `generated` — the tool stamps it automatically on every write.

## Writing conventions

- When a new Source contradicts or updates an existing claim, don't silently overwrite it —
  say what changed and cite the newer source, e.g. "As of June 2026 this is no longer
  accurate: ...[^easa-regulation]". Stale claims should be corrected, not deleted outright.
- Cross-link related pages with standard markdown links to the page filename, e.g.
  `[Mira Kessler](entity-mira-kessler.md)`.
- Keep pages short and dense — bullet points and short paragraphs, not essays.

## Index (`index.md`)

Reserved filename, no `type` required. Body follows OKF §8: one heading per page type
above, each a bullet list of `[Title](filename.md) - description`. Keep it current: every
Wiki Page needs exactly one entry, added or updated as part of any Operation that touches it.

## Log (`log.md`)

Reserved filename. Do not write to it — `write_file` refuses it outright. The surrounding
script appends one dated, newest-first entry per Operation automatically.
