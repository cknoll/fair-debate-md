# Explanatory Example Debate

This document contains an example "debate" to describe the platform *fair-debate* and demonstrate its main features. It will be

1. Persistent in-context-answers
2. Provable integrity of content data

In order to describe the

## Persistent In-Context-Answers

In general, every debate on the platform consists of several *contributions*. A contribution is a sequence of *statements*. Users enter a contribution as ordinary text, which optionally can be stylized using Markdown syntax. This is a simple language to influence text formatting by adding some special characters, e.g. `**bold**` results in **bold** face etc. For more information on Markdown see <https://en.wikipedia.org/wiki/Markdown>.

After submitting a contribution its full text is processed in the following way: Each sentence, each heading, each bullet point or other structure element is considered to be a separate statement and is labeled with its own *statement key*. This makes each statement **referenceable**: You can click/tap on each statement and then copy its URL. Futhermore, each statement can be answered by a new contribution (which again consists of referenceable and answerable statements).

This allows the following hypothetical debate:

- Party P1 starts with an inital contribution (with contribution key `a`). The respective statements are labeled `a1`, `a2`, etc.
- Party P2 does not agree with several points. They answer the seventh statement with a contribution (→ key `a7b`) and the tenth statement with another contribution `a10b`. The statements of these contributions then have the keys: `a7b1`, ... and `a10b1`, ..., respectively. Note that contribution keys end with a letter while statement keys end with a number.
- Now, party P1 wants to point out a misunderstanding and creates contribution `a7b4a`: This contribution is associated to statement 4 of `a7b`.

Each answer-contribution is displayed directly below the statement to which it refers. To improve oversight and clearness different answer-levels can be hidden or unhidden by users.


This approach allows for a very granular discussions where specific points can be addressed very precisely. If necessary a deep back-and-forth discussions can evolve which allows to advance to the root causes of disagreement and potentially generate new insights. At the same time the **overall context is always maintained**. Thus, ripping quotes out of context is impossible and shifting the topic . In addition, due to the availability of the statement keys it is much more feasible to give precise references than in classical online-discussions.


## Provable integrity of content data

As all kinds of infrastructure a discussion platform is operated and controlled by humans. In truly controversial discussions about a polarizing topic there might be the risk that the operator of the discussion platform interferes in the content, e.g. by deletion or manipulation. Another risk is that, e.g. after an argument turned out to be wrong, the platform is falsely accused of manipulation. The approach of *Fair Debate* counters both risks by outsourcing the storage of the content to public git hosting services such as GitHub: Each contribution is stored in a plain text file and committed to a repo. When displaying the current state of the debate the platform does not load the content from a local database. This would be intransparent and allow for undetectable manipulation. Instead the displayed contents are loaded from the public git repos of the participants. Those repos contain the whole change-history and their consistency is ensured by cryptographic hashes. Thus, any manipulation but also any false accusation of manipulation is easily detectable.
