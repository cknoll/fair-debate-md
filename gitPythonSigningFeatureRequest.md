# Feature request for GitPython: create signed commits

Starting point for a separate session. fair-debate wants the platform to sign every
commit it creates (see `konzept_manipulationssicherheit.md`, E4, in the web repo). For
the MVP we shell out to the git CLI; the cleaner route is to add the capability to
GitPython and try to get it merged upstream.

Investigated 2026-08-30 against GitPython 3.1.47.


## The gap is narrower than it looks

GitPython already understands signed commits -- it just cannot produce a signature.

`Commit.__init__` **has** a `gpgsig` parameter:

```
['self', 'repo', 'binsha', 'tree', 'author', 'authored_date', 'author_tz_offset',
 'committer', 'committed_date', 'committer_tz_offset', 'message', 'parents',
 'encoding', 'gpgsig']
```

and `Commit._serialize()` writes it into the object (verified: the `gpgsig` header is
emitted). Reading and round-tripping a signed commit therefore works today.

What is missing is at the two layers above:

```
Commit.create_from_tree(repo, tree, message, parent_commits, head, author, committer,
                        author_date, commit_date, trailers)
                                                   ^ no gpgsig, no signing

IndexFile.commit(self, message, parent_commits, head, author, committer, author_date,
                 commit_date, skip_hooks, trailers)
                                          ^ same
```

So `repo.index.commit(...)` cannot sign, which is the call every GitPython user makes.


## What the feature has to do

1. **Plumb `gpgsig` through** `IndexFile.commit()` -> `Commit.create_from_tree()` ->
   `Commit(...)`. Mechanical, and it alone would already let a caller sign the payload
   themselves and hand the armored signature in. That may be the most upstreamable first
   step: it adds a parameter and no new dependency.

2. **Produce the signature.** Note the ordering trap: the signature covers the
   serialized commit *without* the `gpgsig` header, so the object has to be serialized
   twice -- once as the payload to sign, once with the signature spliced in. Getting
   this wrong yields commits that look fine and verify nowhere.

3. **Respect git's configuration**, so behaviour matches the CLI:
   - `commit.gpgsign` (bool) -- sign by default
   - `user.signingkey` -- which key
   - `gpg.format` -- `openpgp` (default), `ssh`, or `x509`
   - `gpg.program` / `gpg.ssh.program` -- the binary to call

   For `gpg.format = ssh` the signing call is `ssh-keygen -Y sign -f <key> -n git`,
   for openpgp it is `gpg --status-fd=2 -bsau <key>`. Both mean shelling out to an
   external binary -- which GitPython does anyway (it *is* a git wrapper), but it is the
   point most likely to be debated in review, so raise it in the issue before writing
   code.

4. **Verification** (`git log --show-signature` equivalent) is a separate, larger
   feature. Do not bundle it -- signing alone is a self-contained change.


## Suggested approach

- Open an issue at <https://github.com/gitpython-developers/GitPython> first and
  describe the layering above; ask whether a PR that shells out for the signature is
  welcome, or whether only the `gpgsig` passthrough (step 1) is wanted. Search the
  existing issues before opening a new one -- this is an obvious request and may well
  have been raised before; that thread would be the place to continue.
- If only step 1 is wanted, that is still enough for fair-debate: we can call
  `ssh-keygen -Y sign` ourselves and pass the result in, which is much less invasive
  than replacing the whole commit call with CLI invocations.


## What fair-debate does in the meantime

`core.commit_ctb_list()` keeps using `repo.index.commit(...)` until signing lands, then
switches to the git CLI (`repo.git.commit("-S", ...)`) as the MVP solution. Watch out
when changing that call: `author` currently goes in as a `git.Actor` and would become
`--author="Name <mail>"`, and the returned hash would have to come from
`repo.head.commit.hexsha` instead of the return value.


---
---

# Answer from a parallel session (2026-08-31): no upstream PR, use the in-process workaround

Written by a separate Claude Code session (workdir: `just-chatting`) after scanning the
GitPython repository against the plan above. Everything below was verified against
GitHub `main` on 2026-08-30/31. **Decision taken with the user: we do NOT pursue an
upstream change.**


## 1. Status check: the gap is real and still open

- Installed locally: **3.1.46**; latest on PyPI: **3.1.61**.
- On current `main`, `IndexFile.commit()` and `Commit.create_from_tree()` still have
  **no** `gpgsig` parameter and no signing. Nothing has landed since this file was
  written. The analysis above is accurate on that point.


## 2. Why we are not opening a PR — it is not the reason you would expect

The "maintenance mode" wording in the README is misleading. The project is healthy:

| metric | value (2026-08-30) |
|---|---|
| last push | 2026-08-28 |
| open PRs | 2 |
| open issues | 9 (at 5.2k stars) |
| last 5 closed PRs | 5/5 merged, mostly same-day |

Byron even has his own draft PR **#2177 "BREAKING CHANGES for v4.0"** open. And the
README says explicitly: *"there will be no feature development, **unless these are
contributed**"* / *"The project is open to contributions of all kinds"*. So contributed
features are the intended path, and PRs do not rot.

The blocker is **substantive, not organisational**. Issue **#580 "How to gpg sign a
commit?"** contains the maintainer's position verbatim:

> "The low-level plumbing that GitPython provides does not support signing commits."
>
> "you can and probably should resort to using the git command directly, such as in
> `repo.git.commit(<options to enforce a gpg-signature>)`."

That is the documented, never-revised stance and the reason the feature has not existed
for nine years. A PR that shells out to `gpg`/`ssh-keygen` from inside `index.commit()`
and interprets `commit.gpgsign` / `user.signingkey` / `gpg.format` argues directly
against it, and would additionally need CI tests with real key material.
`CONTRIBUTING.md` requires a failing test per contribution and warns: *"A contribution
that works only narrowly but lowers the quality of the codebase may be declined."*

Cost/benefit for fair-debate: we would spend the effort to win an argument we do not
need to win — see section 4, we can sign today with no upstream change at all.


## 3. Correction to "Suggested approach", step 1

**A bare `gpgsig=` passthrough would not actually be usable.** The signature covers the
serialized payload *including the committer timestamp*, which `create_from_tree()` sets
internally (`unix_time = int(time())`). A caller therefore cannot know the payload before
the call and cannot produce a signature to hand in — unless it reimplements `_serialize()`
plus the date/config handling. So step 1 is not the "cheap first step" this file assumed.

If we ever did go upstream, the defensible design is a **signer callback**, not a
`gpgsig` parameter:

```python
def commit(..., sign: Callable[[bytes], str] | None = None)
```

GitPython serializes, calls `sign(payload)`, sets the result as `gpgsig`, serializes
again. No new dependency, no subprocess, no config interpretation, and no GPG in CI —
the test passes `lambda p: "-----BEGIN ..."`. That is the only variant with a real chance
against #580. Noted for the record; we are not doing it.


## 4. What to do instead: sign in-process, no CLI, no patch

All building blocks are already reachable today. Verified in the source on `main`:

- `Commit._calculate_sha_(repo, commit)` **serializes and stores** the object
  (`repo.odb.store(IStream(...))`) and returns the binsha — it does not merely hash.
- `commit.data_stream.read()` yields exactly the payload *without* the `gpgsig` header,
  i.e. precisely the bytes that git signs.

So the double-serialization trap (point 2 of "What the feature has to do") is solved by
letting GitPython do the first serialization for us:

```python
from git import Commit

c = Commit.create_from_tree(repo, repo.index.write_tree(), msg, head=False)
payload = c.data_stream.read()                # exactly what gets signed
c.gpgsig = sign(payload)                      # ssh-keygen -Y sign -f KEY -n git
c.binsha = Commit._calculate_sha_(repo, c)    # writes the signed object
repo.head.set_commit(c, logmsg=f"commit: {msg}")
```

Properties, compared to switching `commit_ctb_list()` to `repo.git.commit("-S", ...)`:

- No duplication of the date/author/encoding/trailer logic — `create_from_tree()` still
  does all of it.
- `author` stays a `git.Actor`; no `--author="Name <mail>"` string building.
- The commit hash still comes back from the call, not from `repo.head.commit.hexsha`.
- Cost: one orphaned *unsigned* commit object per commit, collected by `git gc`. Harmless,
  but worth a comment in the code so nobody is confused by loose objects.
- `_calculate_sha_` is private. It has been stable for years, and the fallback if it ever
  breaks is the CLI route that was the MVP plan anyway. Pin the GitPython version and add
  a test that asserts `git verify-commit` succeeds — that test catches a future break.

**Not executed here** — the source was verified, the snippet itself is untested. Whoever
picks this up should run it against a scratch repo with an SSH signing key first
(`gpg.format = ssh`, `ssh-keygen -Y sign -f <key> -n git`), then confirm with
`git log --show-signature`.


## 5. Net effect on this document

Sections "The gap is narrower than it looks" and "What the feature has to do" stay valid
as analysis. "Suggested approach" is superseded: no issue, no PR. "What fair-debate does
in the meantime" is superseded too — the interim CLI step is unnecessary, go straight to
section 4 above.
