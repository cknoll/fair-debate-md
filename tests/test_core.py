import unittest
import os
from ipydex import IPS, activate_ips_on_exception

import fair_discussion_md as fdmd

activate_ips_on_exception()
pjoin = os.path.join

TESTDATA_DIR = pjoin(os.path.abspath(os.path.dirname(__file__)), "testdata")
TESTDATA1 = pjoin(TESTDATA_DIR, "txt1.md")

class TestCases1(unittest.TestCase):
    def setUp(self):
        with open(TESTDATA1) as fp:
            self.txt1 = fp.read()


        return
    def test_010__core(self):
        md2 = fdmd.add_keys_to_md(self.txt1, prefix="a")
        with open(TESTDATA1.replace(".md", "_tmp.md"), "w") as fp:
            fp.write(md2)

        IPS()