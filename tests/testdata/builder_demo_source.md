---
debate_key: d99-builder-demo
language: en
parties:
  a: Demo A
  b: Demo B
first_commit: 2026-01-01T09:00:00+01:00
hours_between_contributions: 5
---

<!-- !!== label=root party=a ==== -->

# Demo Contribution

This is the first sentence. This is the second one, and it will be answered.

The third sentence mentions the key `a3` of the segment above.

<!-- !!== label=b-answer party=b answers="This is the second one, and it will be answered" ==== -->

This is an answer to statement `a3`. Its own second statement will be answered in turn.

<!-- !!== label=a-deeper party=a answers="Its own second statement will be answered in turn" ==== -->

And this is that answer, one level deeper.
