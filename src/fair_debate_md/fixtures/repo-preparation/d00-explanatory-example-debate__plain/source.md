---
debate_key: d00-explanatory-example-debate
language: en
parties:
  a: Explainer
  b: Elaborator
  c: Questioner
first_commit: 2026-08-24T08:00:00+02:00
hours_between_contributions: 5
---

<!-- !!== label=root party=a ==== -->

# Explanatory Example Debate

This document is a *debate*. Its purpose is to describe and motivate the main features of *Fair Debate* — the platform you are looking at. Please be aware that this document kind of abuses the platforms functionality (i.e. the special way to display a stream of speech and counter-speech) for explanations. Actually Fair Debate is not meant for displaying documentation but as tool for constructive and relieable communication about possibly controversal topics.

You are reading the opening *contribution* of this debate. It has the contribution key `a`. Every contribution is split automatically into *segments* — headings, sentences, bullet points. The segments of a contribution carry keys of their own like `a1`, `a2`, etc. Therefore each segment can be precisely referenced. And each segment can be answered on its own. Hovering over a statement shows its key, clicking/tapping it additionally allows to copy its URL and to reply to it.

Statements that are highlighted have been answered already. Click one such answered segment to unfold the replies below it. Most of this document lives in those answers, so unfolding them is how you read it.

Multiple parties (users) can participate in a debate. Parties are identified by letters, assigned in the order in which they join a debate.

- `a` is the party that opens the debate, which here is me.
- `b` is the first party to answer.
- `c` is the second party to answer.
- Further parties continue the alphabet and beyond (see below).

A party may also answer a statement of its own. That is how a later addition can be introduced to the debate instead of rewriting what was already published.

Two main features set this platform apart from an ordinary comment section or forum. They are explained in the answers.

1. Persistent in-context answers.
2. Provable integrity of the content data.

If you have understood those main features you can use Fair Debate pretty well. However, there are some more details you might be interested in.

## FAQ (answers are will be given soon)

- What happens if more parties join the debate then there are letters in the alphabet?
- Is it possible to answer multiple segments or parts of segments?
- How can the integrity of a debate (i.e. the absence of manipulation) be checked?
- How does the project collect feedback?
- Is it possible to help the project?

<!-- !!== label=b-intro party=b answers="`b` is the first party to answer" ==== -->

That is me. My role in this debate is to add details.

<!-- !!== label=c-intro party=c answers="`c` is the second party to answer" ==== -->

And that is me. I ask (sometimes critical) questions and try to find flaws.

<!-- !!== label=b-answers party=b answers="Persistent in-context answers" ==== -->

This answer is bound to the first entry of that list, and it is a contribution in its own right. Because it refers to statement `{{anchor}}`, its key is `{{key}}`, and its own statements are keyed `{{key}}1`, `{{key}}2`, and so on.

What that arrangement enables:

- An answer appears directly underneath the statement it refers to. **A statement is therefore tied to its context twice — by its key and by the place where it is shown.** Whole levels of answers can be folded away when a page gets crowded.
- An answer is set apart from the surrounding contribution by colour and indentation, such that readers always know the text of which party they are reading.
- Any number of parties can take part, each with its own letter. By the way, that letter becomes part of the key of any contribution by that party (see the example below).
- Contributions may be written in Markdown.

Because the context of an answer is by technical means tied to the segment, quoting any party out of context does not work. The surrounding text (and thus the original context) is at most one click away.

<!-- !!== label=a-example party=a answers="Any number of parties can take part" ==== -->

### An example

Consider a debate with three parties.

- Party `a` opens it with the initial contribution `a`. Its segments (also called "statements") are keyed `a1`, `a2` and so on.
- Party `b` disagrees with two points. They answer statement 7 with a contribution keyed `a7b`, and statement 10 with another one keyed `a10b`. The statements inside those contributions are keyed `a7b1`, `a7b2` and `a10b1`, `a10b2`. Note that a contribution key ends with a letter, a statement key with a number.
- Party `c` joins, reads the exchange and answers statement 4 of `a7b`. Their contribution is `a7b4c`.
- Party `a` returns to clear up a misunderstanding in the second statement of that answer, which produces `a7b4c2a`.

A key is a path. Read from left to right it names every step from the opening contribution down to the answer in front of you, which is why no answer can be detached from what it responds to.

### Why this is worth the trouble

A discussion becomes granular. A single point can be addressed precisely, and a disagreement can be followed down to the level where it actually starts — often an assumption that neither side had stated. Meanwhile the wider context is never lost, because every contribution stays anchored where it belongs. And since every statement has a key, referring to something precisely costs nothing.

<!-- !!== label=a-markdown party=a answers="Contributions may be written in Markdown" ==== -->

Markdown adds formatting through a handful of plain characters — `**bold**` produces **bold**, for instance. A short introduction is at <https://en.wikipedia.org/wiki/Markdown>.

<!-- !!== label=b-integrity party=b answers="Provable integrity of the content data" ==== -->

### Why this matters

Like any infrastructure, a discussion platform is run by people. In a genuinely contested debate there is a risk that whoever operates the platform interferes with the content, by deleting or by altering it. A second risk points the other way — that an operator is accused of having done so although they did not, for instance after an argument turned out badly for the side making the accusation.

By providing technical means for independent manipulation checks this platform can form a neutral ground for controversal debates.

### How it is done

*Fair Debate* answers both risk by keeping the content out of its own database. Each contribution is a plain text file, committed to a version-controlled publicly readable repository, one per debate, and the platform renders a debate by reading those files. When a user publishes a contribution this creates a new commit with a timestamp, a fingerprint and a cryptographic signature, and since each fingerprint is computed over the previous one as well, the commits form a chain. Altering an old contribution afterwards changes every fingerprint from that point onwards.

This might seem like irrelevant technical detail but signed commits to publicly readable repositories enable *everyone* to detect a manipulation (via changed fingerprints) and to prove that (with the cryptographic commit signatures). This is a fundamental difference to classic online publishing where whoever controls the server can control (and thus change) what it displays. Users could save screenshots but they could never prove that these are not faked.

Every contribution carries a link (click the magnifier symbol) to the integrity page of the debate. There the fingerprints are listed and the repository with the signed commits can be downloaded. Additionally, that page describes how to check for manipulation of the content.

### Current status

Establishing a really waterproof system for integrity checks which is still understandable for most users is actually not trivial. The current approach thus is a compromise and work in progress. However, it already provides a lot more safety than what is usual.

<!-- !!== label=c-critical party=c answers="is a compromise" ==== -->

What are the weak points of this approach?

<!-- !!== label=a-evolution party=a answers="What are the weak points of this approach?" ==== -->

Currently there are the following weak points:

### Usability

- The repositories can be downloaded as `.zip` files (including the whole history inside `.git/`) but serving them as a clonable *git remote* would be much more convenient. This feature is on the TODO-list.
- Checking the fingerprints and signatures of the commits currently needs some technical expertise (e.g. running shell commands). This could be simplified with dedicated software but that software should be managed or at least audited by an independent entity. A verification tool controlled by the same instance it should verify is pointless.

### Actual integrity

- The platform could renew its public key and thus deny any commit signature based on the old key. However, this would affect any debate and thus severely harm the credibility of the platform. Furthermore it is planned to publish the public key on trusted places (such as ...).
- There will be situations when changing the commit history is necessary. E.g. this explanatory repo has to be updated along with the software, or unlawful contributions have to be removed from the platform. Currently a clean way to handle and document such cases is not yet implemented.
- The debate-integrity-concept and its implementation have not yet been audited by independent experts. It is thus not unlikely that Fair Debate is affected by security flaws. But this is a general problem with software and being aware of it usually is an important step in preventing critical incidents.


<!-- !!== label=a-selfreply party=a answers="A party may also answer a statement of its own" ==== -->

This contribution demonstrates exactly that. It was written by party `a` and it answers a statement of party `a`, and such a self-answer is marked as one, so that nobody mistakes it for a reply by somebody else.

