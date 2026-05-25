import unittest
import os
from textwrap import dedent as twdd
import tempfile

from bs4 import BeautifulSoup
import pytest

from ipydex import IPS, activate_ips_on_exception

import fair_debate_md as fdmd

from fair_debate_md.utils import compare_strings

activate_ips_on_exception()
pjoin = os.path.join

TESTDATA_DIR = pjoin(os.path.abspath(os.path.dirname(__file__)), "testdata")
FIXTURE_DIR = fdmd.fixtures.path
TESTDATA1 = pjoin(FIXTURE_DIR, "txt1.md")

TEST_REPO1_DIR = fdmd.fixtures.TEST_REPO1_DIR


# Note: expected tree assumes byte-order sort (LC_ALL=C.UTF-8) for determinism
# across locales/CI environments. `tree` is invoked with LC_ALL=C.UTF-8 in the
# tests below (UTF-8 variant is required so `tree` still emits the Unicode
# box-drawing characters, while collation remains byte-wise).
TEST_REPO1_EXPECTED_TREE = twdd(
    """
    .
    ├── a
    │   ├── a.md
    │   └── a2b1a.md
    └── b
        ├── a2b.md
        ├── a2b1a3b.md
        ├── a4b.md
        ├── a6b.md
        └── a7b.md

    3 directories, 7 files
    """
).lstrip("\n")


class TestCases1(unittest.TestCase):
    def setUp(self):
        self.key_prefix = "::a"
        self.dirs_to_remove = []
        with open(TESTDATA1) as fp:
            self.txt1 = fp.read()
        return

    def tearDown(self) -> None:
        for dirpath in self.dirs_to_remove:
            dirpath = os.path.abspath(dirpath)
            # try to prevent the accidental deletion of important dir
            assert "testdata" in dirpath or "fixtures" in dirpath or "/tmp" in dirpath
            fdmd.utils.tolerant_rmtree(dirpath)
        return super().tearDown()

    def _mk_temp_dir(self, remove_in_tear_down=True):
        tempdir_path = tempfile.mkdtemp(prefix="fdmd_")
        if remove_in_tear_down:
            self.dirs_to_remove.append(tempdir_path)

        return tempdir_path

    def _setup_test_repo1(self, remove_in_tear_down=True):
        tempdir_path = self._mk_temp_dir(remove_in_tear_down=remove_in_tear_down)
        fdmd.unpack_repos(tempdir_path)
        repo1_path = pjoin(tempdir_path, fdmd.TEST_DEBATE_KEY)

        return repo1_path

    def save_debug_result(self, result, suffix=".md"):
        # useful if result changes or for debugging
        debug_fpath = TESTDATA1.replace(".md", f"_debug{suffix}")
        with open(debug_fpath, "w") as fp:
            fp.write(result)

    def _unpack_d00_explanatory_example_debate_repo(self, patches=False):
        import shutil

        repo_key = "d00-explanatory-example-debate"
        tempdir_path = self._mk_temp_dir()
        # content_path = pjoin(FIXTURE_DIR, "repo-preparation", f"{repo_key}__plain")
        self.content_path = pjoin("__FIXTURES_RP__", f"{repo_key}__plain")
        target_dir_path = pjoin(tempdir_path, repo_key)
        shutil.rmtree(target_dir_path, ignore_errors=True)

        if patches:
            flag = " --patches"
        else:
            flag = ""
        cmd = f"fdmd process-content-dir {self.content_path} {target_dir_path}{flag}"
        return_value = os.system(cmd)
        self.assertEqual(return_value, 0)  # check that command exited without error

        return target_dir_path

    def test_012__add_keys_to_md(self):

        md_src = (
            "This is the *first* sentence. Then `comes` another *sentence*. Finally the **last** one."
        )
        mdp = fdmd.MDProcessor(md_src)
        segmented_html = mdp.convert()
        self.assertEqual(segmented_html.count("<span"), 3)

    def test_011__add_keys_to_md(self):

        repo_path = self._unpack_d00_explanatory_example_debate_repo(patches=True)
        repo_parent_path = os.path.dirname(repo_path)
        ddl = fdmd.load_repo(repo_parent_path, debate_key="d00-explanatory-example-debate", new_debate=False)
        self.assertIn("This is an answer to statement", ddl.final_html)

        self.assertIn("<code>a14</code>", ddl.final_html)

    def test_013__handle_abbreviations(self):

        md_src = (
            "Some text including some abbreviations, i.e. strings like "
            "e.g. 'w.r.t. something' or 'bspw.' etc. Now this is a new sentence. "
            "This also, w.r.t. something different."
        )
        mdp = fdmd.MDProcessor(md_src)
        segmented_html = mdp.convert()
        self.assertEqual(segmented_html.count("<span"), 3)

    def test_014__process_p_tag(self):
        html_src = "<p>Ut <em>quiquia <strong>eius</strong> dolorem</em> voluptatem. Adipisci sit adipisci non est.</p>"
        pka = fdmd.ProtoKeyAdder(html_src, prefix="k")
        pka.add_proto_keys_to_html()
        res = str(pka.soup)
        expected_res = (
            "<p>::k Ut <em>quiquia <strong>eius</strong> dolorem</em> voluptatem."
            " ::k  Adipisci sit adipisci non est.</p>"
        )
        self.assertEqual(res, expected_res)

    def test_021__add_spans(self):
        tag1 = "<h1>::a1 Ipsum non ut est.</h1>"

        sa = fdmd.SpanAdder(fdmd.MDProcessor(), tag1, key_prefix=self.key_prefix)
        res = sa.add_spans_for_keys()
        res_expected = '<h1><span class="segment" id="a1"> Ipsum non ut est.</span></h1>'
        self.assertEqual(res, res_expected)

    def test_022__add_spans(self):
        tag2 = (
            "<p>::a2 Ut <em>quiquia <strong>eius</strong> dolorem</em> voluptatem."
            " ::a3 <strong>Adipisci sit adipisci non est</strong>.</p>"
        )

        sa = fdmd.SpanAdder(fdmd.MDProcessor(), tag2, key_prefix=self.key_prefix)
        res = sa.add_spans_for_keys()

        res_expected = (
            '<div class="p_level0"><span class="segment" id="a2"> Ut <em>quiquia <strong>eius</strong>'
            " dolorem</em> voluptatem.</span>"
            '<span class="segment" id="a3"> <strong>Adipisci sit adipisci non est</strong>.</span></div>'
        )

        self.assertEqual(res, res_expected)

    def test_023__add_spans(self):
        tag3 = (
            "<p>::a2 Ut <em>quiquia <strong>eius</strong> dolorem</em> voluptatem."
            " ::a3 <strong>Adipisci sit adipisci non est</strong>."
            " ::a4 Dolor etincidunt neque sed tempora porro quiquia."
            " ::a5 Porro velit non consectetur numquam velit.</p>"
        )

        sa = fdmd.SpanAdder(fdmd.MDProcessor(), tag3, key_prefix=self.key_prefix)
        res = sa.add_spans_for_keys()
        res_expected = (
            '<div class="p_level0"><span class="segment" id="a2"> Ut <em>quiquia <strong>eius</strong>'
            " dolorem</em> voluptatem.</span>"
            '<span class="segment" id="a3"> <strong>Adipisci sit adipisci non est</strong>.</span>'
            '<span class="segment" id="a4"> Dolor etincidunt neque sed tempora porro quiquia.</span>'
            '<span class="segment" id="a5"> Porro velit non consectetur numquam velit.</span></div>'
        )
        self.assertEqual(res, res_expected)

    def test_024__add_spans(self):
        html_src = twdd(
            """
        <ul>
        <li>::a6 Ipsum velit adipisci</li>
        <li>
        <p>::a7 Adipisci est magnam etincidunt sed:</p>
        <ul>
        <li>::a8 <code>some code</code> Sed etincidunt etincidunt</li>
        <li>
        <p>::a9 sit aliquam eius quiquia.</p>
        <ul>
        <li>::a10 Ut etincidunt magnam ut etincidunt <code>some code</code></li>
        <li>::a11 quiquia quisquam porro.<ul>
        <li>::a12 Ut modi dolor est labore velit non.</li>
        </ul>
        </li>
        </ul>
        </li>
        </ul>
        </li>
        </ul>
        """
        )

        res_expected = twdd(
            """
        <ul>
        <li><span class="segment" id="a6"> Ipsum velit adipisci</span></li>
        <li>
        <div class="p_level0"><span class="segment" id="a7"> Adipisci est magnam etincidunt sed:</span></div>
        <ul>
        <li><span class="segment" id="a8"> <code>some code</code> Sed etincidunt etincidunt</span></li>
        <li>
        <div class="p_level0"><span class="segment" id="a9"> sit aliquam eius quiquia.</span></div>
        <ul>
        <li><span class="segment" id="a10"> Ut etincidunt magnam ut etincidunt <code>some code</code></span></li>
        <li><span class="segment" id="a11"> quiquia quisquam porro.</span><ul>
        <li><span class="segment" id="a12"> Ut modi dolor est labore velit non.</span></li>
        </ul>
        </li>
        </ul>
        </li>
        </ul>
        </li>
        </ul>
        """
        )

        sa = fdmd.SpanAdder(fdmd.MDProcessor(), html_src, key_prefix=self.key_prefix)
        res = sa.add_spans_for_keys()
        self.assertEqual(res, res_expected)

    def test_040__load_debate_dir(self):
        test_debate_dir = self._setup_test_repo1()
        ddl = fdmd.load_dir(test_debate_dir, debate_key=fdmd.TEST_DEBATE_KEY)
        self.assertIsNotNone(ddl.final_html)
        soup = BeautifulSoup(ddl.final_html, "html.parser")
        wrapper_div = soup.find(id="contribution_a")
        self.assertGreater(len(wrapper_div.attrs["data-debate-key"]), 0)
        # IPS(-1)

    def test_050__rollout_patches1(self):
        patch_dir = pjoin(TEST_REPO1_DIR, "patches_01")
        test_repo1_workdir = f"{TEST_REPO1_DIR}_workdir"
        self.dirs_to_remove.append(test_repo1_workdir)
        fdmd.repo_handling.rollout_patches(repo_dir=test_repo1_workdir, patch_dir=patch_dir)

        expected_result = TEST_REPO1_EXPECTED_TREE

        # generate tree output (requires probably unix)
        # Force byte-order sorting (LC_ALL=C.UTF-8) so output is deterministic across
        # locales (local dev vs. CI).
        res = (
            fdmd.utils.get_cmd_output(
                f"tree {test_repo1_workdir}", extra_env={"LC_ALL": "C.UTF-8"}
            )
            .replace(test_repo1_workdir, ".")
            .replace("\xa0", " ")
        )  # replace strange space
        self.assertEqual(res, expected_result)

    def test_060__cli_unpack_repos(self):

        tempdir_path = self._mk_temp_dir()

        cmd = f"fdmd unpack-repos {tempdir_path}"
        os.system(cmd)

        repo_path = pjoin(tempdir_path, fdmd.TEST_DEBATE_KEY)

        # Force byte-order sorting (LC_ALL=C.UTF-8) for deterministic `tree` output.
        res = (
            fdmd.utils.get_cmd_output(f"tree {repo_path}", extra_env={"LC_ALL": "C.UTF-8"})
            .replace(repo_path, ".")
            .replace("\xa0", " ")
        )  # replace strange space

        expected_result = TEST_REPO1_EXPECTED_TREE
        self.assertEqual(res, expected_result)

    def test_070__cli_unpack_repos(self):
        # TODO: improve this test such that its adaption to content updates is easier (or unnecessary)
        repo_path = self._unpack_d00_explanatory_example_debate_repo()

        # Force byte-order sorting (LC_ALL=C.UTF-8) for deterministic `tree` output.
        res = (
            fdmd.utils.get_cmd_output(f"tree {repo_path}", extra_env={"LC_ALL": "C.UTF-8"})
            .replace(repo_path, ".")
            .replace("\xa0", " ")
        )  # replace strange space

        expected_tree = (
            ".\n├── a\n│   ├── a.md\n│   ├── a14b12a.md\n│   ├── a14b15a.md\n"
            "│   └── a14b6a.md\n└── b\n    ├── a14b.md\n    ├── a15b.md\n    └── a20b.md\n\n3 directories, 7 files\n"
        )

        self.assertEqual(res, expected_tree)

        repo_path = self._unpack_d00_explanatory_example_debate_repo(patches=True)
        res = (
            fdmd.utils.get_cmd_output(f"tree {repo_path}", extra_env={"LC_ALL": "C.UTF-8"})
            .replace(repo_path, ".")
            .replace("\xa0", " ")
        )  # replace strange space

        expected_tree = (
            ".\n├── a\n│   ├── a.md\n│   ├── a14b12a.md\n│   ├── a14b15a.md\n│   └── a14b6a.md\n├── b\n"
            "│   ├── a14b.md\n│   ├── a15b.md\n│   └── a20b.md\n"
            "└── patches_01\n    ├── 0001-automatic-contribution.patch\n    "
            "├── 0002-automatic-contribution.patch\n    "
            "└── 0003-automatic-contribution.patch\n\n4 directories, 10 files\n"
        )

        self.assertEqual(res, expected_tree)

    def test_080_a(self):
        _TEST_CASES = [
            # (label, markdown_source, expected_indent)
            (
                "4-space simple",
                "- level 0\n    - level 1\n",
                4,
            ),
            (
                "2-space simple",
                "- level 0\n  - level 1\n",
                2,
            ),
            (
                "4-space ordered",
                "1. first\n    1. nested\n",
                4,
            ),
            (
                "2-space ordered",
                "1. first\n  1. nested\n",
                2,
            ),
            (
                "no nesting -> default",
                "- a\n- b\n- c\n",
                2,
            ),
            (
                "4-space with fenced code block containing fake list",
                "- item\n    - nested\n\n```\n  - not a list\n    - also not\n```\n",
                4,
            ),
            (
                "2-space with fenced code block containing fake list",
                "- item\n  - nested\n\n```\n    - not a list\n```\n",
                2,
            ),
            (
                "4-space with tilde fenced code block",
                "- item\n    - nested\n\n~~~\n  - code\n~~~\n",
                4,
            ),
            (
                "2-space deeply nested",
                "- a\n  - b\n    - c\n      - d\n",
                2,
            ),
            (
                "4-space deeply nested",
                "- a\n    - b\n        - c\n",
                4,
            ),
            (
                "tabs get expanded (tab = 4 spaces)",
                "- a\n\t- b\n",
                4,
            ),
        ]


        def _run_detect_tests() -> None:
            for label, src, expected in _TEST_CASES:
                got = fdmd.utils.detect_list_indent(src)
                status = "OK" if got == expected else "FAIL"
                print(f"[{status}] {label}: expected={expected}, got={got}")
                assert got == expected, f"{label}: expected {expected}, got {got}"

        _run_detect_tests()




class TestKeyHelpers(unittest.TestCase):
    """Tests for key_regex widening and new key helper functions."""

    def test_key_regex_single_char_tokens(self):
        import re
        from fair_debate_md.core import key_regex
        self.assertIsNotNone(key_regex.match("a5"))
        self.assertIsNotNone(key_regex.match("b12"))
        self.assertIsNotNone(key_regex.match("z1"))

    def test_key_regex_multi_char_tokens(self):
        from fair_debate_md.core import key_regex
        self.assertIsNotNone(key_regex.match("aa5"))
        self.assertIsNotNone(key_regex.match("ab12"))
        self.assertIsNotNone(key_regex.match("zz99"))

    def test_key_regex_no_match_uppercase(self):
        from fair_debate_md.core import key_regex
        self.assertIsNone(key_regex.match("A5"))
        self.assertIsNone(key_regex.match("B3"))

    def test_key_regex_no_match_digit_start(self):
        from fair_debate_md.core import key_regex
        self.assertIsNone(key_regex.match("5a"))
        self.assertIsNone(key_regex.match("3b"))

    def test_decompose_key_single_char(self):
        from fair_debate_md.core import decompose_key
        self.assertEqual(decompose_key("a5"), ["a5"])
        self.assertEqual(decompose_key("b1"), ["b1"])
        self.assertEqual(decompose_key("a304b1"), ["a304", "b1"])
        self.assertEqual(decompose_key("a3ab"), ["a3", "ab"])

    def test_decompose_key_multi_char_tokens(self):
        from fair_debate_md.core import decompose_key
        self.assertEqual(decompose_key("aa5"), ["aa5"])
        self.assertEqual(decompose_key("ab12"), ["ab12"])
        self.assertEqual(decompose_key("a3ab"), ["a3", "ab"])
        self.assertEqual(decompose_key("aa5ab3"), ["aa5", "ab3"])
        self.assertEqual(decompose_key("aa5ab3b"), ["aa5", "ab3", "b"])

    def test_is_valid_key_multi_char_tokens(self):
        from fair_debate_md.core import is_valid_key
        self.assertTrue(is_valid_key("aa5"))
        self.assertTrue(is_valid_key("ab12"))
        self.assertTrue(is_valid_key("aa5ab3"))
        self.assertTrue(is_valid_key("aa5ab3b"))
        self.assertFalse(is_valid_key("5a"))
        self.assertFalse(is_valid_key("AA5"))

    def test_get_contribution_key(self):
        from fair_debate_md.core import get_contribution_key
        self.assertEqual(get_contribution_key("a5", "c"), "a5c")
        self.assertEqual(get_contribution_key("a304b1", "a"), "a304b1a")
        self.assertEqual(get_contribution_key("a5", "b"), "a5b")
        self.assertEqual(get_contribution_key("aa5", "ab"), "aa5ab")

    def test_get_last_token(self):
        from fair_debate_md.core import get_last_token
        self.assertEqual(get_last_token("a5c3b"), "b")
        self.assertEqual(get_last_token("a3ab"), "ab")
        self.assertEqual(get_last_token("a5"), None)
        self.assertEqual(get_last_token("aa5ab3"), None)
        self.assertEqual(get_last_token("aa5ab3b"), "b")
        self.assertEqual(get_last_token("a5c"), "c")


class TestMultipleContributions(unittest.TestCase):
    """Tests for multiple direct replies per segment (T2)."""

    def _make_ddl(self, tree_content: dict):
        from fair_debate_md.core import DebateDirLoader, MDProcessor

        ddl = DebateDirLoader(dirpath="/tmp/dummy_test_fdmd", debate_key="test-debate")
        for key, md_with_real_keys in tree_content.items():
            ddl.tree[key] = MDProcessor(
                key_prefix=key, md_with_real_keys=md_with_real_keys, db_ctb=False
            )
        ddl.handle_root_mdp()
        return ddl

    def test_single_reply_regression(self):
        ddl = self._make_ddl({
            "a": "::a1 Statement one. ::a2 Statement two.",
            "a1b": "::a1b1 Single reply from b.",
        })
        ddl.generate_html_with_contributions()
        soup = BeautifulSoup(ddl.final_html, "html.parser")

        self.assertIsNotNone(soup.find(id="contribution_a1b"))
        childs = ddl.root_mdp.contribution_childs["a1"]
        self.assertIsInstance(childs, list)
        self.assertEqual(len(childs), 1)
        self.assertEqual(childs[0].key_prefix, "a1b")

    def test_two_replies_both_present(self):
        ddl = self._make_ddl({
            "a": "::a1 Statement one. ::a2 Statement two.",
            "a1b": "::a1b1 Reply from b.",
            "a1c": "::a1c1 Reply from c.",
        })
        ddl.generate_html_with_contributions()
        soup = BeautifulSoup(ddl.final_html, "html.parser")

        self.assertIsNotNone(soup.find(id="contribution_a1b"))
        self.assertIsNotNone(soup.find(id="contribution_a1c"))

    def test_two_replies_deterministic_order(self):
        ddl = self._make_ddl({
            "a": "::a1 Statement one.",
            "a1b": "::a1b1 Reply from b.",
            "a1c": "::a1c1 Reply from c.",
        })
        ddl.generate_html_with_contributions()
        soup = BeautifulSoup(ddl.final_html, "html.parser")

        all_ids = [tag["id"] for tag in soup.find_all(id=True)]
        idx_b = all_ids.index("contribution_a1b")
        idx_c = all_ids.index("contribution_a1c")
        self.assertLess(idx_b, idx_c, "contribution_a1b must appear before contribution_a1c")

    def test_contribution_childs_is_list(self):
        ddl = self._make_ddl({
            "a": "::a1 Statement one.",
            "a1b": "::a1b1 Reply from b.",
            "a1c": "::a1c1 Reply from c.",
        })
        ddl.generate_html_with_contributions()
        childs = ddl.root_mdp.contribution_childs["a1"]
        self.assertIsInstance(childs, list)
        self.assertEqual(len(childs), 2)
        self.assertEqual(childs[0].key_prefix, "a1b")
        self.assertEqual(childs[1].key_prefix, "a1c")

    def test_no_duplication_on_repeated_call(self):
        ddl = self._make_ddl({
            "a": "::a1 Statement one.",
            "a1b": "::a1b1 Reply from b.",
            "a1c": "::a1c1 Reply from c.",
        })
        ddl.generate_html_with_contributions()
        ddl.generate_html_with_contributions()
        childs = ddl.root_mdp.contribution_childs["a1"]
        self.assertEqual(len(childs), 2, "Repeated call must not duplicate contribution_childs entries")

    def test_three_replies_order(self):
        ddl = self._make_ddl({
            "a": "::a1 Statement one.",
            "a1b": "::a1b1 Reply from b.",
            "a1c": "::a1c1 Reply from c.",
            "a1d": "::a1d1 Reply from d.",
        })
        ddl.generate_html_with_contributions()
        soup = BeautifulSoup(ddl.final_html, "html.parser")

        all_ids = [tag["id"] for tag in soup.find_all(id=True)]
        idx_b = all_ids.index("contribution_a1b")
        idx_c = all_ids.index("contribution_a1c")
        idx_d = all_ids.index("contribution_a1d")
        self.assertLess(idx_b, idx_c)
        self.assertLess(idx_c, idx_d)


def remove_trailing_spaces(txt):
    return "\n".join([line.rstrip(" ") for line in txt.split("\n")])
