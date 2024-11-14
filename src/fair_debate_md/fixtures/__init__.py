import os
pjoin = os.path.join

path = os.path.abspath(os.path.dirname(__file__))
TEST_REPO1_DIR = pjoin(path, "repos", "d1-lorem_ipsum")

txt1_md_fpath = os.path.join(path, "txt1.md")
