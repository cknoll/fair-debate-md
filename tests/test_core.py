import unittest
import os
from textwrap import dedent as twdd
import tempfile

from bs4 import BeautifulSoup

from ipydex import IPS, activate_ips_on_exception

import fair_debate_md as fdmd

from fair_debate_md.utils import compare_strings

activate_ips_on_exception()
pjoin = os.path.join

TESTDATA_DIR = pjoin(os.path.abspath(os.path.dirname(__file__)), "testdata")
FIXTURE_DIR = fdmd.fixtures.path
TESTDATA1 = pjoin(FIXTURE_DIR, "txt1.md")

TEST_REPO1_DIR = fdmd.fixtures.TEST_REPO1_DIR


TEST_REPO1_EXPECTED_TREE = twdd(
    """
    .
    ├── a
    │   ├── a2b1a.md
    │   └── a.md
    └── b
        ├── a2b1a3b.md
        ├── a2b.md
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

    def test_010__add_keys_to_md(self):

        # small part for easier debugging:

        N = 148

        txt1 = self.txt1[:N]

        mdp = fdmd.MDProcessor(txt1)
        md2 = mdp.add_proto_keys_to_md(txt1, prefix="k", early_placeholder_replacement=True).rstrip()

        expected_result_fpath = TESTDATA1.replace(".md", "_with_proto_keys.md").replace(
            FIXTURE_DIR, TESTDATA_DIR
        )

        with open(expected_result_fpath, "r") as fp:
            md2_expected = fp.read()

        N2 = 164
        md2_ex = md2_expected[:N2]

        self.assertEqual(md2, md2_ex)


        # now the full content
        mdp = fdmd.MDProcessor(self.txt1)
        md2 = mdp.add_proto_keys_to_md(self.txt1, prefix="k", early_placeholder_replacement=True)
        expected_result_fpath = TESTDATA1.replace(".md", "_with_proto_keys.md").replace(
            FIXTURE_DIR, TESTDATA_DIR
        )

        if 0:
            self.save_debug_result(md2)
            return

        with open(expected_result_fpath, "r") as fp:
            md2_expected = fp.read()

        md2 = remove_trailing_spaces(md2)
        self.assertEqual(md2, md2_expected)

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

    def test_030__get_html_with_segments(self):

        # test empty string
        _, res = fdmd.core._convert_plain_md_to_segmented_html("")
        self.assertEqual(res, "")

        # test simple string
        _, res = fdmd.core._convert_plain_md_to_segmented_html("foo bar")
        res_expected = '<div class="p_level0"><span class="segment" id="a1"> foo bar</span></div>'

        # we do conversion twice because the backend currently does so
        # (to handle inline code-tags with _strip_me_ attribute)
        res_expected = str(BeautifulSoup(res_expected, "html.parser").prettify())
        res_expected = str(BeautifulSoup(res_expected, "html.parser"))
        self.assertEqual(res, res_expected)

        # test full file
        md_with_real_keys, res = fdmd.core._convert_plain_md_to_segmented_html(self.txt1)

        if 0:
            self.save_debug_result(res, suffix="_pretty.md")

        expected_result_fpath = pjoin(TESTDATA_DIR, "txt1_segmented_html.html")
        with open(expected_result_fpath, "r") as fp:
            res_expected = fp.read()

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
        res = (
            fdmd.utils.get_cmd_output(f"tree {test_repo1_workdir}")
            .replace(test_repo1_workdir, ".")
            .replace("\xa0", " ")
        )  # replace strange space
        self.assertEqual(res, expected_result)

    def test_060__cli_unpack_repos(self):

        tempdir_path = self._mk_temp_dir()

        cmd = f"fdmd unpack-repos {tempdir_path}"
        os.system(cmd)

        repo_path = pjoin(tempdir_path, fdmd.TEST_DEBATE_KEY)

        res = (
            fdmd.utils.get_cmd_output(f"tree {repo_path}").replace(repo_path, ".").replace("\xa0", " ")
        )  # replace strange space

        expected_result = TEST_REPO1_EXPECTED_TREE
        self.assertEqual(res, expected_result)

    def test_070__cli_unpack_repos(self):
        repo_path = self._unpack_d00_explanatory_example_debate_repo()

        res = (
            fdmd.utils.get_cmd_output(f"tree {repo_path}").replace(repo_path, ".").replace("\xa0", " ")
        )  # replace strange space

        expected_tree = (
            ".\n├── a\n│   ├── a14b6a.md\n│   ├── a5b2a.md\n│   └── a.md\n└── b\n"
            "    ├── a14b.md\n    └── a15b.md\n\n3 directories, 5 files\n"
        )

        self.assertEqual(res, expected_tree)

        repo_path = self._unpack_d00_explanatory_example_debate_repo(patches=True)
        res = (
            fdmd.utils.get_cmd_output(f"tree {repo_path}").replace(repo_path, ".").replace("\xa0", " ")
        )  # replace strange space

        expected_tree = (
            ".\n├── a\n│   ├── a14b6a.md\n│   ├── a5b2a.md\n│   └── a.md\n├── b\n│   ├── a14b.md\n│   "
            "└── a15b.md\n└── patches_01\n    ├── 0001-automatic-contribution.patch\n    "
            "├── 0002-automatic-contribution.patch\n    "
            "└── 0003-automatic-contribution.patch\n\n4 directories, 8 files\n"
        )

        self.assertEqual(res, expected_tree)


def remove_trailing_spaces(txt):
    return "\n".join([line.rstrip(" ") for line in txt.split("\n")])
