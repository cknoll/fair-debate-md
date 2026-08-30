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
