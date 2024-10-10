import unittest

import fair_discussion_md as fdmd

class TestCases1(unittest.TestCase):
    def test_010__core(self):
        fdmd.core.main()