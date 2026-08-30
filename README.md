[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# Markdown Support Code for Fair Debate

Backend support library for [fair-debate-web](../fair-debate-web). It turns plain markdown
contributions into segmented, individually referenceable HTML and manages the key system that
links replies to the exact segments they respond to.

## Concept in a nutshell

A debate is a tree of contributions. Each contribution is split into referenceable **segments**;
any segment can be answered, and an answer is itself made of referenceable segments.

Keys encode the reply path. In a key like `a5c3b`:

- the letter runs are **role-tokens** — they identify a party *within a debate*
  (`a` = original poster, `b` = first responder, `c` = next new party, …);
- the digits are segment indices.

So `a5c3b` reads: party `a`'s segment 5 → answered by party `c`, whose segment 3 → answered by
party `b`.

Properties:

- **Arbitrarily many participants per debate.** Role-tokens are allocated per debate
  (`a`, `b`, …, `z`, then multi-character `aa`, `ab`, …), so a debate is not limited to two
  sides. Role-tokens are scoped to a single debate — the same user may be `b` in one debate and
  `f` in another.
- **A single segment can receive replies from several parties** (e.g. `a5b`, `a5c`, `a5d`).
- **Flexible references:** a reply can reference a range of sequential segments (`a5-7b` =
  reply to segments 5–7) or a word range within one segment (`a7_4-8b` = reply to words 4–8
  of segment `a7`). The reference is encoded in the key itself, so debates remain verifiable
  from the raw `.md` files alone. Keys are unique, but overlapping references by the same
  party are allowed.

See `docs/multi_party_concept.md` for the multi-party design and
`docs/flexible_references_concept.md` for the flexible-reference design (including the
frozen word-tokenizer specification).

## Installation

- clone repo
- `pip install -e .`  (or `uv pip install -e .`)

Requires Python >= 3.11.

## Usage

Bring the web app's working directory into a defined state (unpack fixture repos):

- `fdmd unpack-repos ./content_repos`

Build a content repo from a debate written as a single markdown file (its front matter
carries the debate key and the parties, marker comments separate the contributions -- see
`fair_debate_md/debate_builder.py`):

- `fdmd build-debate-repo ./my-debate.md`
- `fdmd build-debate-repo ./my-debate.md --repo-into ./my-debate --patches-into ./patches`

Transform a plain directory of markdown files (`<party>/<key>.md`) into a repo with keys.
Without `--patches` this writes the keyed files only -- the git repo is created by the
patch step:

- `fdmd process-content-dir ./my-debate__plain ./my-debate --patches`

For the sources of the fixture debates see
`src/fair_debate_md/fixtures/repo-preparation/README.md`.

## Testing

- `pytest`

Some tests shell out to `git` and `tree`, so both must be installed and a git identity
(`user.name` / `user.email`) must be configured.

## Coding style

We use `black -l 110 ./` to ensure coding style consistency. For commit messages we (now) try to
follow the [conventional commits specification](https://www.conventionalcommits.org/en/).
