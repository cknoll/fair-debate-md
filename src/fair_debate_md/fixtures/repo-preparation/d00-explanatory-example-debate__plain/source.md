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

This document is a *debate*, and its subject is *Fair Debate* — the platform you are looking at. Reading it should be enough to understand how this place works.

You are reading the opening *contribution* of this debate. Every contribution is split automatically into *statements* — a sentence, a heading, a bullet point. Each statement carries a key of its own and can therefore be referenced and answered on its own. Hovering over a statement shows its key, clicking it shows its full URL.

Statements that are highlighted have been answered already. Click one to unfold the answers below it. Most of this document lives in those answers, so unfolding them is how you read it.

Parties are identified by letters, assigned in the order in which they join a debate.

- `a` is the party that opens the debate, which here is me.
- `b` is the first party to answer.
- `c` is the second party to answer.
- Further parties continue the alphabet, for as long as a debate attracts them.

A party may also answer a statement of its own. That is how a later addition gets a place of its own instead of quietly rewriting what was already published.

Two properties set this platform apart from an ordinary comment section.

1. Persistent in-context answers.
2. Provable integrity of the content data.

<!-- !!== label=b-intro party=b answers="`b` is the first party to answer" ==== -->

That is me. Where the opening text is too brief, I take it apart and add what it skips.

<!-- !!== label=c-intro party=c answers="`c` is the second party to answer" ==== -->

And that is me. I ask the questions that a text written by a platform about itself tends to leave out.

<!-- !!== label=b-answers party=b answers="Persistent in-context answers" ==== -->

This answer hangs on the first entry of that list, and it is a contribution in its own right. Because it refers to statement `{{anchor}}`, its key is `{{key}}`, and its own statements are keyed `{{key}}1`, `{{key}}2`, and so on.

What that arrangement buys you:

- An answer appears directly underneath the statement it refers to. **A statement is therefore tied to its context twice — by its key and by the place where it is shown.** Whole levels of answers can be folded away when a page gets crowded.
- An answer is set apart from the surrounding contribution by colour and indentation, so it stays visible whose text you are reading.
- Any number of parties can take part, each with its own letter and its own colour.
- Contributions may be written in Markdown.

Because the context travels with the statement, quoting somebody out of context does not work here. The surrounding text is always one click away, and it stays there.

<!-- !!== label=a-example party=a answers="Any number of parties can take part" ==== -->

### An example

Consider a debate with three parties.

- Party `a` opens it. Their statements are keyed `a1`, `a2` and so on.
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

Like any infrastructure, a discussion platform is run by people. In a genuinely contested debate there is a risk that whoever operates it interferes with the content, by deleting or by altering it. A second risk points the other way — that an operator is accused of having done so although they did not, for instance after an argument turned out badly for the side making the accusation.

### How it is done

*Fair Debate* answers both by keeping the content out of its own database. Each contribution is a plain text file, committed to a version-controlled repository, one per debate, and the platform renders a debate by reading those files. Publishing records a commit with a timestamp and a fingerprint, and since each fingerprint is computed over the previous one as well, the commits form a chain. Altering an old contribution afterwards changes every fingerprint from that point onwards.

Every contribution carries a link to the integrity page, where the fingerprints and the commit chain of this debate can be read and exported. Anyone who notes them down can detect a later change, so nobody has to be appointed to keep watch.

<!-- !!== label=c-critical party=c answers="nobody has to be appointed to keep watch" ==== -->

A chain of fingerprints shows that a repository has not been rewritten since you read it. It does not show where that repository came from.

Two things follow, and neither is comfortable.

- The repositories of this instance live on the same server as the platform. Whoever runs that server can rebuild a repository from scratch and publish it. The chain would be intact afterwards. It would simply be a different chain, and a reader arriving today has nothing to compare it against.
- This very document is a case in point. It ships with the platform's source code and is rebuilt whenever the explanation changes, and its commit dates are generated. The debate explaining provable integrity is not itself a debate whose integrity you could check.

So what is actually proven here today?

<!-- !!== label=a-evolution party=a answers="So what is actually proven here today?" ==== -->

Less than the name promises, and the integrity page says so too — under the heading of what it does not prove yet.

The mechanism itself is real and it works. Contributions are files, publishing writes commits, commits carry fingerprints, and those fingerprints can be read and exported. What is missing is what would make them count against a determined operator: repositories owned by the parties themselves, mirrored somewhere this instance does not control. Until that exists, the guarantee holds against a quiet edit — anyone who noted a fingerprint will notice — and not against rebuilding everything at once.

The second objection is simply true. This document is a fixture. It is generated from source files, its commit dates are made up, and it will be rebuilt again once the platform changes and the explanation stops fitting. Staging it as though it had grown the way a real debate grows would have been the more elegant choice, and the less honest one.

<!-- !!== label=a-selfreply party=a answers="A party may also answer a statement of its own" ==== -->

This contribution demonstrates exactly that. It was written by party `a` and it answers a statement of party `a`, and such a self-answer is marked as one, so that nobody mistakes it for a reply by somebody else.

It also does what the statement above describes. By the time it was written, two further parties had answered the opening text — which that text could not have mentioned, having been published before them. Rather than editing it afterwards and pretending it had known all along, the addition arrives here, as a contribution of its own, with its own place in the commit chain.
