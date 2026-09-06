---
debate_key: d00-explanatory-example-debate
language: en
parties:
  a: Explainer
  b: Elaborator
  c: Questioner
first_commit: 2026-08-24T08:00:00+02:00
hours_between_contributions: [4, 8]
active_hours: [8, 22]
---

<!-- !!== label=root party=a ==== -->

# Explanatory Example Debate

This document is a *debate*. Its purpose is to describe and motivate the main features of *Fair Debate* — the platform you are looking at. Please be aware that this document kind of abuses the platform's functionality (i.e. the special way to display a stream of speech and counter-speech) for explanations. Actually Fair Debate is not meant for displaying documentation but as tool for constructive and reliable communication about possibly controversial topics.

You are reading the opening *contribution* of this debate. It has the contribution key `a`. Every contribution is split automatically into *segments* — headings, sentences, bullet points. The segments of a contribution carry keys of their own like `a1`, `a2`, etc. Therefore each segment can be precisely referenced. And each segment can be answered on its own. Hovering over a segment shows its key; clicking or tapping it also lets you copy its URL and answer it.

Top right of the header sits an ![info](/static/img/info-icon.svg) symbol, an `i` in a circle. It switches on help mode: from then on the interface explains its own controls. Click an element to see its explanation, or step through all of them in turn with the arrows. The key `i` switches the mode on and off as well.

Segments that are highlighted have been answered already. Click one such answered segment to unfold the answers below it. Most of this document lives in those answers, so unfolding them is how you read it.

Multiple parties (users) can participate in a debate. Parties are identified by letters, assigned in the order in which they join a debate.

- `a` is the party that opens the debate, which here is me.
- `b` is the first party to answer.
- `c` is the second party to answer.
- Further parties continue the alphabet.

A party may also answer a segment of its own. That is how a later addition can be introduced to the debate instead of rewriting what was already published.

Two main features set this platform apart from an ordinary comment section or forum. They are explained in the answers.

1. Persistent in-context answers.
2. Provable integrity of the content data.

If you have understood those main features you can use Fair Debate pretty well.

The format alone, though, does not make a debate a good one. Everybody who writes here commits themselves to six rules — among them keeping in mind that one may be wrong, separating description from judgement, and correcting one's own mistakes. The full text is published as the *self-commitment to a constructive debate culture* at [/rules](/rules/).

How the interface is used and what to keep in mind while writing is documented at [/docs](/docs/). Questions about the platform and the project, such as moderation or how to support it, are answered at [/faq](/faq/).

<!-- !!== label=b-intro party=b answers="`b` is the first party to answer" ==== -->

That is me. My role in this debate is to add details.

<!-- !!== label=c-intro party=c answers="`c` is the second party to answer" ==== -->

And that is me. I ask (sometimes critical) questions and try to find flaws. By the way, one thing does not add up here. The opening contribution already knows that there will be a party `b` and a party `c`, and speaks of us before either of us had written a word. So this debate was not held, it was composed.

<!-- !!== label=a-chronology party=a answers="So this debate was not held, it was composed" ==== -->

That is correct, and it is worth saying out loud. The opening contribution says at the very beginning that this document abuses the platform's functionality for explanations, and this is where that shows. A real debate grows forwards and nobody in it knows who will answer next.

<!-- !!== label=b-answers party=b answers="Persistent in-context answers" ==== -->

This answer is bound to the first entry of that list, and it is a contribution in its own right. Because it refers to segment `{{anchor}}`, its key is `{{key}}`, and its own segments are keyed `{{key}}1`, `{{key}}2`, and so on.

What that arrangement enables:

- An answer appears directly underneath the segment it refers to. **A segment is therefore tied to its context twice — by its key and by the place where it is shown.** Whole levels of answers can be folded away when a page gets crowded.
- An answer is set apart from the surrounding contribution by colour and indentation, such that readers always know the text of which party they are reading.
- Any number of parties can take part, each with its own letter. By the way, that letter becomes part of the key of any contribution by that party (see the example below).
- Contributions may be written in Markdown.

Because the context of an answer is by technical means tied to the segment, quoting any party out of context does not work. The surrounding text (and thus the original context) is at most one click away.

<!-- !!== label=a-example party=a answers="Any number of parties can take part" ==== -->

### An example

Consider a debate with three parties.

- Party `a` opens it with the initial contribution `a`. Its segments are keyed `a1`, `a2` and so on.
- Party `b` disagrees with two points. They answer segment 7 with a contribution keyed `a7b`, and segment 10 with another one keyed `a10b`. The segments inside those contributions are keyed `a7b1`, `a7b2` and `a10b1`, `a10b2`. Note that a contribution key ends with a letter, a segment key with a number.
- Party `c` joins, reads the exchange and answers segment 4 of `a7b`. Their contribution is `a7b4c`.
- Party `a` returns to clear up a misunderstanding in the second segment of that answer, which produces `a7b4c2a`.

A key is a path. Read from left to right it names every step from the opening contribution down to the answer in front of you, which is why no answer can be detached from what it responds to.

### Why this is worth the trouble

A discussion becomes granular. A single point can be addressed precisely, and a disagreement can be followed down to the level where it actually starts — often an assumption that neither side had stated. Meanwhile the wider context is never lost, because every contribution stays anchored where it belongs. And since every segment has a key, referring to something precisely costs nothing.

<!-- !!== label=a-markdown party=a answers="Contributions may be written in Markdown" ==== -->

Markdown adds formatting through a handful of plain characters — `**bold**` produces **bold**, for instance. A short introduction is at <https://en.wikipedia.org/wiki/Markdown>.

<!-- !!== label=b-integrity party=b answers="Provable integrity of the content data" ==== -->

### Why this matters

Like any infrastructure, a discussion platform is run by people. In a genuinely contested debate there is a risk that whoever operates the platform interferes with the content, by deleting or by altering it. A second risk points the other way — that an operator is accused of having done so although they did not, for instance after an argument turned out badly for the side making the accusation.

By providing technical means for independent manipulation checks this platform can form a neutral ground for controversial debates.

### How it is done

*Fair Debate* answers both risks by keeping the content out of its own database. Each contribution is a plain text file, committed to a version-controlled publicly readable repository, one per debate, and the platform renders a debate by reading those files. When a user publishes a contribution this creates a new commit with a timestamp, a fingerprint and a cryptographic signature, and since each fingerprint is computed over the previous one as well, the commits form a chain. Altering an old contribution afterwards changes every fingerprint from that point onwards.

This might seem like irrelevant technical detail but signed commits to publicly readable repositories enable *everyone* to detect a manipulation (via changed fingerprints) and to prove that (with the cryptographic commit signatures). This is a fundamental difference to classic online publishing where whoever controls the server can control (and thus change) what it displays. Users could save screenshots but they could never prove that these are not faked.

### Why the signature matters

Without it, a fingerprint you saved is only your own claim, and the operator can answer that you wrote that file yourself. The signature makes it a statement of the platform. By signing a commit, the platform attests that this is the version it published — so if two differently signed versions of the same history turn up, it stands behind both, and one of them must be wrong. The only excuse left is that the key was stolen, which is not a comfortable position either.

The signature travels with the repository, so anyone who clones it holds that evidence. In a contested debate the opposing side has the strongest interest of all in keeping such a copy, and so do interested observers such as journalists.

### Where to look

Every contribution carries a link (click the ![magnifier](/static/img/integrity-magnifier.svg) symbol) to the integrity page of the debate. There the fingerprints are listed, and the repository with the signed commits can be downloaded as a single file or cloned directly with git. Additionally, that page describes how to check for manipulation of the content.

For anyone taking part in a debate the shortest route is to clone that repository once. From then on a single `git pull --ff-only` does the checking. It passes quietly while the debate merely grows, and it refuses to run the moment the history was rewritten. Nothing has to be noted down and nothing has to be remembered, and the refusal leaves the reader holding both versions at once, which is what turns a suspicion into something showable.

### What is promised, and what is not

The platform cannot promise that the commit history is never changed. There might be cases where content has to be removed from the history (e.g. personal information). We instead promise that every change to the history is visible. It breaks the chain of fingerprints, and it will be reported on the integrity page of the debate it concerns. A broken chain with no such report means manipulation.

However, the exact procedure for such a removal is not specified yet.

### Current status

Establishing a really waterproof system for integrity checks which is still understandable for most users is actually not trivial. The current approach thus is a compromise and work in progress. However, it already provides a lot more safety than what is usual.

This debate (along with some others) is a demonstration fixture. Its repo is rebuilt whenever the explanation changes, so its authors, its commits, their times and their fingerprints are made up, although the integrity page shows them as it would for a real debate. For the debates that people actually hold here, everything described above applies unchanged.

<!-- !!== label=c-critical party=c answers="is a compromise" ==== -->

What are the weak points of this approach?

<!-- !!== label=a-evolution party=a answers="What are the weak points of this approach?" ==== -->

Currently there are the following weak points:

### Usability

- Checking the fingerprints and signatures of the commits currently needs some technical expertise (e.g. running shell commands). This could be simplified with dedicated software but that software should be managed or at least audited by an independent entity. A verification tool controlled by the same instance it should verify is pointless.

### Actual integrity

- The bad actor scenario here is a denial rather than an attack. Faced with two signed versions of the same history, the platform could claim that its signing key had been stolen and that one of those signatures is therefore not its own. Nothing inside the repository refutes that on its own. What would help is a copy of the repository kept by an independent and trustworthy third party, and that is not implemented yet. The risk itself is small, since a signing key leaving the platform is an unlikely event. Key changes may still become necessary for ordinary reasons, and those are harmless. As long as a key change does not come together with a conflict in the commit history, there is nothing to explain.
- There will be situations when changing the commit history is necessary. E.g. this explanatory repo has to be updated along with the software, or unlawful contributions have to be removed from the platform. Currently a clean way to handle and document such cases is not yet implemented.
- The debate-integrity-concept and its implementation have not yet been audited by independent experts. It is thus not unlikely that Fair Debate is affected by security flaws. But this is a general problem with software and being aware of it usually is an important step in preventing critical incidents.
- A fingerprint shows that a text has not changed since it was published. It does not show who wrote it. The commits are created and signed by this platform, not by the authors, so the platform could in principle put a contribution under somebody's name. Signatures by the contributors themselves would close that gap and do not exist here yet.
- The platform could show one history to one reader and a different one to another, and sign both. That is only noticed when the two readers compare, which is precisely what a public mirror of the repositories would automate. There is none yet.
- Whoever controls the server controls the signing key, the administrators of the data centre included. That risk comes with any IT infrastructure. What malicious actors, however, cannot do is take back the signatures already handed out. A manipulation therefore stays detectable and can be resolved.


<!-- !!== label=a-selfreply party=a answers="A party may also answer a segment of its own" ==== -->

This is one. It was written by party `a` and answers a segment of party `a`, and the platform marks it as a self-answer so that nobody mistakes it for somebody else's. The useful case is not this demonstration but the correction. An addition or an admission of error ends up right next to the sentence it concerns, instead of somewhere far below where nobody reading the original will see it.
