# Debate "{debate_key}"

This repository holds the contributions of one debate on {platform_name}, one plain
markdown file per contribution. The platform renders the debate by reading these files --
they are the content itself, not an export of it.

It was published at {debate_url}. If that address no longer answers, the debate may have
moved or the instance may be gone; the repository in your hands is unaffected either way.
Background on the project: {background_url}

## Why this repository exists

A platform that keeps debates in its own database can change them, and nobody outside can
tell. In contrast on {platform_name} every contribution is a commit, every commit carries a
fingerprint computed over all the preceding ones, and every commit is signed by the platform.
Altering an old contribution changes its fingerprint and everyone after it. The fingerprints
make manipulation detectable while the signatures can prove that a commit history is "official"
(and not just staged by somebody who falsely accuses the platform of manipulation).

That is what your copy is for. You do not have to do anything with it. Having it is the
point. It is only needed as reinsurance to detect and prove manipulation.

## How to check it

The platform's public key is in the file `allowed_signers`, added with the first commit of
this repository.

    git -c gpg.ssh.allowedSignersFile=./allowed_signers log --show-signature

`Good "git" signature` on every commit means the history is intact and was published by
whoever holds that key.

    git log --format="%H  %ci"

lists every commit with its fingerprint and time, newest first. If you noted a fingerprint
down earlier -- from the integrity page of the debate, or from an older copy of this
repository -- look for it here. Present means nothing before it was altered. Missing means
the history was rewritten.

`git fsck` does **not** answer this question. It only checks that the stored data matches
its own fingerprints, and a rewritten history passes that test, because the rewrite
produces new and internally consistent fingerprints. Only a comparison against a value kept
outside the server settles it.

## What this does not prove

- **Who wrote a contribution.** The commits are created and signed by the platform, not by
  the authors. A fingerprint shows that a text has not changed since it was published, not
  who wrote it.
- **That the key belongs to who it claims.** It is the platform's own key, handed out by
  the platform. What it does give you is that the *same* key signed everything you have --
  so two contradictory histories signed by it convict whoever holds it.
- **That nothing was ever removed.** A contribution may have to disappear for legal
  reasons. Doing that means rewriting the history, which breaks the chain visibly; such an
  event is meant to be announced and explained on the debate's integrity page.

## Work in progress

The integrity concept behind this repository is still being built, and no independent
expert has reviewed it. Two gaps worth naming, so you do not have to find them yourself:

- There is **no procedure for renewing the signing key** yet. If the key ever changes,
  nothing here says how old signatures relate to the new one. This is a solvable issue but
  details need to be specified.
- There is no public mirror and no external archive yet. The only independent copies of
  this history are the ones readers keep. Yours is one of them.
