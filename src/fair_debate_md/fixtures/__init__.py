import os

pjoin = os.path.join

path = os.path.abspath(os.path.dirname(__file__))

rp_path = pjoin(path, "repo-preparation")

TEST_REPO_HOST_DIR = pjoin(path, "repos")
TEST_REPO1_DIR = pjoin(TEST_REPO_HOST_DIR, "d1-lorem_ipsum")

txt1_md_fpath = os.path.join(path, "txt1.md")
