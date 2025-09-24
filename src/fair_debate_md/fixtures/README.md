This directory contains data for several repositories in form of a sequence of patches.

To create a new (patchified) repo the following chain of commands can help:


```
git init
git add a/a.md
git commit --author="user_a <user_a@example.org>" -m "my contribution"
git add b/a14b.md
git commit --author="user_b <user_b@example.org>" -m "my contribution"
```

or for more files

```
git init
git add a/a.md
git commit --author="user_a <user_a@example.org>" -m "my contribution"
git add b/a2b.md b/a4b.md b/a6b.md b/a7b.md
git commit --author="user_b <user_b@example.org>" -m "my contribution"
git add a/a2b1a.md
git commit --author="user_a <user_a@example.org>" -m "my contribution"
git add b/a2b1a3b.md
git commit --author="user_b <user_b@example.org>" -m "my contribution"
```

Create patches:

```
git format-patch --root -o patches
```

Apply patches:

```
git init
git am patches/*patch
```
