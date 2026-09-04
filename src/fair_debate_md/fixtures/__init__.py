import os

pjoin = os.path.join

path = os.path.abspath(os.path.dirname(__file__))

rp_path = pjoin(path, "repo-preparation")

TEST_REPO_HOST_DIR = pjoin(path, "repos")
TEST_REPO1_DIR = pjoin(TEST_REPO_HOST_DIR, "d1-lorem_ipsum")

# Which of the fixture debates may appear on a public instance.
#
# Everything under `repos/` exists for the test suites, and none of it can be deleted --
# every one of the fifteen is named by tests in this package or in the web app. But a
# deployment used to roll out all of them and load the *test* database fixture as its
# initial data, which put `d1-lorem_ipsum` and three debates literally named
# "test_debate" on the landing page of the public instance.
#
# So the split is a role, not a deletion: tests get everything, a deployment gets these.
# A debate belongs here when a first-time visitor should be able to read it and come away
# with a correct impression of what the platform is for.
#
# d30 and d32 joined on 2026-09-04 as demonstration pieces for two features that the
# argued-out debates do not show -- a party count that overflows the legend, and answers
# pointing at segment and word ranges. Both say in their second segment that they are
# constructed and what for, because their content cannot say it for them: d32's topic is
# trivial on purpose and d30's text is placeholder text. d30 is `hidden` on the instance
# (reachable by link, not listed): lorem ipsum has no business on a landing page, and
# most of its parties hold no account, which its introduction announces.
DEMO_DEBATE_KEYS = (
    "d00-explanatory-example-debate",       # what the landing page links to (english)
    "d01-erklaerende-beispieldebatte",      # its german counterpart
    "d30-many-parties",                     # 25 parties; hidden on the instance, see above
    "d31-ice-cream",                        # a small dispute with nesting and several parties
    "d32-overlapping-refs",                 # answers pointing at segment and word ranges
    "d33-wachstum-klimaschutz",             # students argue growth vs. climate, after a radio debate
    "d34-pazifismus-ukraine",               # pacifism and the war in Ukraine, from a podcast episode
    "d35-rente-generationengerechtigkeit",  # pension reform, argued out, ends in a concession
    "d36-handyverbot-schule",               # phone ban at schools, left unfinished for live demos
)

txt1_md_fpath = os.path.join(path, "txt1.md")
