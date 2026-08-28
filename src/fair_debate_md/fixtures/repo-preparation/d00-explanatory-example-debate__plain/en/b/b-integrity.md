### Why this matters

Like any infrastructure, a discussion platform is run by people. In a genuinely contested debate there is a risk that whoever operates it interferes with the content, by deleting or by altering it. A second risk points the other way — that an operator is accused of having done so although they did not, for instance after an argument turned out badly for the side making the accusation.

### How it is done

*Fair Debate* answers both by keeping the content out of its own database. Each contribution is a plain text file, committed to a version-controlled repository, one per debate, and the platform renders a debate by reading those files. Publishing records a commit with a timestamp and a fingerprint, and since each fingerprint is computed over the previous one as well, the commits form a chain. Altering an old contribution afterwards changes every fingerprint from that point onwards.

Every contribution carries a link to the integrity page, where the fingerprints and the commit chain of this debate can be read and exported. Anyone who notes them down can detect a later change, so nobody has to be appointed to keep watch.
