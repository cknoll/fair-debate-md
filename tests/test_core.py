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
        md2 = fdmd.add_keys_to_md(self.txt1, prefix="k")
        expected_result_fpath = TESTDATA1.replace(".md", "_with_proto_keys.md")

        if 0:
            # useful if result changes or for debugging
            with open(expected_result_fpath, "w") as fp:
                fp.write(md2)
            return

        with open(expected_result_fpath, "r") as fp:
            md2_expected = fp.read()

        self.assertEqual(md2, md2_expected)