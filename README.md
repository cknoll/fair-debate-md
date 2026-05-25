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
- A given party has at most one direct answer to a given segment (it can be edited).

See `docs/multi_party_concept.md` for the full design.

## Installation

- clone repo
- `pip install -e .`  (or `uv pip install -e .`)

Requires Python >= 3.11.

## Usage

Bring the web app's working directory into a defined state (unpack fixture repos):

- `fdmd unpack-repos ./content_repos`

Transform a plain directory of markdown files into a repo with keys:

- `fdmd process-content-dir __FIXTURES_RP__/d00-explanatory-example-debate__plain ./d00-explanatory-example-debate --patches`

## Testing

- `pytest`

Some tests shell out to `git` and `tree`, so both must be installed and a git identity
(`user.name` / `user.email`) must be configured.

## Coding style

We use `black -l 110 ./` to ensure coding style consistency. For commit messages we (now) try to
follow the [conventional commits specification](https://www.conventionalcommits.org/en/).
