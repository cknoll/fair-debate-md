import re
import os
import glob
import types
import json
import logging
import collections

import markdown
import markdownify as mdf
from bs4 import BeautifulSoup, element
import git

from ipydex import IPS

from . import utils
from . import repo_handling
from .key_management import ProtoKeyAdder

pjoin = os.path.join

TEST_DEBATE_KEY = "d1-lorem_ipsum"

# this should be the same as in the web-application
logger = logging.getLogger("fair-debate")
logger.debug("fair_debate_md.core loaded")


def convert_tabs_to_spaces(input_string):
    lines = input_string.splitlines()

    def replace_tabs(line):
        leading_tabs = len(re.match(r"^\t*", line).group(0))
        return " " * (leading_tabs * 4) + line.lstrip("\t")

    converted_lines = [replace_tabs(line) for line in lines]
    return "\n".join(converted_lines)


class KeyAdder:
    """
    Convert proto-keys to numbered keys
    """

    def __init__(self, md_src: str):
        self.md_src = md_src

    def replace_proto_key_by_numbered_key(self, proto_key: str, prefix: str):
        res = []
        parts = self.md_src.split(proto_key)
        for i, part in enumerate(parts[:-1], start=1):
            res.append(part)
            new_key = f'{proto_key.replace("k", prefix)}{i}'
            res.append(new_key)
        res.append(parts[-1])

        return "".join(res)


class SpanAdder:
    def __init__(
        self, parent_mdp, html_src: str, key_prefix: str, contribution_childs: dict[str, "MDProcessor"] = None
    ):
        self.parent_mdp: MDProcessor = parent_mdp
        self.html_src = html_src
        self.key_prefix = key_prefix
        self.soup = BeautifulSoup(html_src, "html.parser")
        self.pattern = r" ?(XXX\d+)".replace("XXX", self.key_prefix)
        self.span_tag_is_open = False
        self.encoded_left_delimiter = "_[_"
        self.encoded_right_delimiter = "_]_"

        # TODO: for historical reasons this level is 1 based
        # calculated by level = len(decompose_key(key)), where key is an arbitrary segment key of this html src
        # in the web app we use 0-based level
        self.level: int = None

        # this dict serves to add divs after the spans which contain contributions
        if contribution_childs is None:
            contribution_childs = {}
        self.contribution_childs = contribution_childs

        self.active_tag_stack = []

        # compiled regex
        self.cre = re.compile(self.pattern)

    def add_spans_for_keys(self, prettify: bool = False) -> str:
        root = self.soup
        self.process_children(root=root, level=0)

        # we have to convert the soup to a flat string because of our handling of encoded delimiters
        res = str(root)
        res2 = self.insert_encoded_delimiters(res)

        self.add_contributions(res2)
        res3 = self.convert_soup_to_final_html(prettify=prettify)
        return res3

    def convert_soup_to_final_html(self, prettify: bool = False):

        if self.parent_mdp.is_root_mdp:
            # wrap with div to add metadata (debate-key)
            container_tag = self.soup.new_tag("div", id="contribution_a")
            container_tag.attrs["data-debate-key"] = self.parent_mdp.debate_key
            # this tag intentionally has no content.
            # purpose: it allows the js-logic of the web app to treat the a-contribution as "contribution"
            root_segment_tag = self.soup.new_tag("div", id="root_segment")
            container_tag.append(root_segment_tag)
            container_tag.extend(self.soup)
            self.soup = container_tag

            if self.parent_mdp.is_root_mdp and self.parent_mdp.additional_css_classes:
                additional_class_str = " ".join(self.parent_mdp.additional_css_classes)
                self.soup.attrs["class"] = additional_class_str
                self.soup.attrs["data-plain_md_src"] = json.dumps(self.parent_mdp.plain_md_src)

        self.convert_code_placeholders()

        # convert to flat string
        if prettify:
            flat_html = str(self.soup.prettify())
            return self.decode_strip_me_tags(flat_html)
        else:
            return self.decode_strip_me_tags()

    def decode_strip_me_tags(self, flat_html=None):
        # TODO: this only needs to be done for the top level (currently self.level == 1)
        # IPS(self.key_prefix == "::a")

        if flat_html is not None:
            new_soup = BeautifulSoup(flat_html, "html.parser")
        else:
            new_soup = self.soup
        for code_block in new_soup.find_all(name="code"):
            if code_block.get("_strip_me_") == "True":
                code_block.string.replace_with(code_block.string.strip())
                del code_block["_strip_me_"]

        return str(new_soup)

    def convert_code_placeholders(self):
        """
        insert back the original content of the replaced code blocks
        """
        for code_block in self.soup.find_all(name="code"):

            # `.text` is like "::code_placeholder_0::"
            key = code_block.text
            if rplmt := self.parent_mdp._code_element_contents.get(key):
                code_block.string.replace_with(rplmt)

            if code_block.string == code_block.string.strip():
                code_block["_strip_me_"] = "True"

    def add_contributions(self, html_src: str) -> None:
        """
        Add div tags for contributions (if they exist).

        :param html_src:    html source with segment-spans but without contribution-divs
        """

        # TODO: probably we could use the existing soup here?
        self.soup = BeautifulSoup(html_src, "html.parser", preserve_whitespace_tags=["code"])

        all_segments = self.soup.find_all("span", class_="segment")
        assert all_segments, "The must be at least one segment"
        segment_dict: dict[str, element.Tag] = dict([(s.attrs["id"], s) for s in all_segments])

        first_key = all_segments[0].attrs["id"]
        self.level = len(decompose_key(first_key))

        self._process_contribution_childs(segment_dict)

        # replace the p-tags in the original (outermost) text
        # (for deeper levels this has already been done)
        # TODO: unify level-definition with web application
        if self.level == 1:
            self._replace_p_with_div(self.soup, level=0)

    def _process_contribution_childs(self, segment_dict):
        """

        :param segment_dict:    dict of segment elements in the parent
                                (will be referenced by the contributions)

        """
        for key, mdp in self.contribution_childs.items():

            contribution_content = mdp.get_html_with_segments()
            contribution_soup = BeautifulSoup(contribution_content, "html.parser")
            # here the use of `level` is consistent with the web app:
            # current level (e.g. 1 (= number of key-parts) is applied to contribution_soup)
            self._replace_p_with_div(contribution_soup, self.level)
            additional_class_str = " ".join(mdp.additional_css_classes)
            class_str = f"contribution level{self.level} {additional_class_str}".strip()

            attribute_dict = {"class": class_str, "id": f"contribution_{mdp.key_prefix}"}
            if mdp.add_plain_md_as_data:
                # Note this attribute must be allowed by bleach (in settings.py of the web app)
                attribute_dict["data-plain_md_src"] = json.dumps(mdp.plain_md_src)

            contribution_div = self.soup.new_tag("div", attrs=attribute_dict)
            contribution_div.extend(contribution_soup)
            referenced_segment = segment_dict[key]
            segment_parent = referenced_segment.parent
            if segment_parent.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                # special treatment of answer-contributions to headings (styling reasons)
                wrapper_div = self.soup.new_tag("div", attrs={"class": "answered_heading"})

                # insert empty wrapper
                segment_parent.insert_after(wrapper_div)

                # remove segment_parent (h2, etc)
                segment_parent.extract()

                wrapper_div.append(segment_parent)
                segment_parent.insert_after(contribution_div)
                class_list = segment_parent.attrs.get("class", "").split(" ")
                class_list.append("heading")
                segment_parent.attrs["class"] = " ".join(class_list).strip()
            else:
                referenced_segment.insert_after(contribution_div)

    def _replace_p_with_div(self, part_soup: BeautifulSoup, level: int):
        """
        It seems like nested p tags get "corrected" by some downstream processing.
        To prevent this, we convert p tags into special div-tags
        """
        p_tags: list[element.Tag] = part_soup.find_all("p")
        for p_tag in p_tags:
            new_div = part_soup.new_tag("div", attrs={"class": f"p_level{level}"})

            saved_contents = list(p_tag.contents)

            # Copy the contents of the <p> tag to the new <div> tag
            new_div.extend(saved_contents)

            # Replace the <p> tag with the new <div> tag
            p_tag.replace_with(new_div)

    def is_new_paragraph_tag(self, elt: element.PageElement):
        return getattr(elt, "name", None) in ("ul", "ol", "p")

    def close_tag(self, parent_tag: element.Tag, tag_name: str = "span"):
        parent_tag.append(self.encode_tags(f"</{tag_name}>"))
        self.active_tag_stack[-1].span_tag_is_open = False
        self.span_tag_is_open = False

    def process_children(self, root: element.Tag, level: int):
        original_children = list(root.children)
        next_children = [*original_children[1:], element.NavigableString("")]
        root.clear()
        for current_child, next_child in zip(original_children, next_children):
            new_child_list = self.process_child(current_child, level=level + 1)
            root.extend(new_child_list)

            if self.is_new_paragraph_tag(next_child) and root.span_tag_is_open:
                self.close_tag(root, "span")

        if self.active_tag_stack and self.active_tag_stack[-1].span_tag_is_open:
            self.close_tag(root, "span")

        return root

    def process_child(self, child: element.PageElement, level: int) -> list:
        if isinstance(child, element.Tag):
            self.active_tag_stack.append(child)
            child.span_tag_is_open = None
            res = [self.process_children(root=child, level=level)]
            self.active_tag_stack.pop()
            return res

        assert isinstance(child, element.NavigableString)
        matches = list(self.cre.finditer(child.text))
        if not matches:
            return [child]
        start_idcs = []
        end_idcs = []
        keys = []
        for match in matches:
            start_idcs.append(match.start())
            end_idcs.append(match.end())
            delimiter_key = match.group(1)  # something like " ::a1"
            key = delimiter_key.replace("::", "").lstrip()  # a1
            keys.append(key)

        # add final index at the end of the string
        # start_idcs.append(len(child.text))

        new_str_parts = []

        content_index = 0

        for i0, i1, key in zip(start_idcs, end_idcs, keys):
            content = child.text[content_index:i0]
            content_index = i1
            new_str_parts.append(content)

            if self.span_tag_is_open:
                new_str_parts.append(self.encode_tags("</span>"))
            new_str_parts.append(self.encode_tags(f'<span class="segment" id="{key}">'))
            self.active_tag_stack[-1].span_tag_is_open = True
            self.span_tag_is_open = True

        new_str_parts.append(child.text[content_index:])  # add final content
        res = element.NavigableString("".join(new_str_parts))
        return [res]

    def encode_tags(self, txt):
        return txt.replace("<", self.encoded_left_delimiter).replace(">", self.encoded_right_delimiter)

    def insert_encoded_delimiters(self, txt):
        return txt.replace(self.encoded_left_delimiter, "<").replace(self.encoded_right_delimiter, ">")


class MDProcessor:

    def __init__(
        self,
        plain_md: str = None,
        proto_key_prefix="k",
        key_prefix="a",
        md_with_real_keys: str = None,
        # store whether this is a data-base contribution (i.e. not yet committed)
        db_ctb: bool = None,
        convert_now=False,
    ):
        self.plain_md_src = plain_md
        self.additional_css_classes = []
        self.add_plain_md_as_data = False

        self.proto_key_prefix = proto_key_prefix
        self.key_prefix = key_prefix

        self.md_with_proto_keys: str = None
        self.md_with_real_keys = md_with_real_keys
        self.db_ctb: bool = db_ctb
        self.segmented_html: str = None
        self.contribution_childs: dict[str, MDProcessor] = {}
        self.is_root_mdp: bool = False
        self.debate_key: str = None
        self.cached_keys: list = None

        self._code_element_contents = {}
        self._early_placeholder_replacement = False

        # convenience: save one line in the caller
        if convert_now:
            self.convert()

    def convert(self) -> str:
        self.convert_plain_md_to_md_with_proto_keys()
        self.convert_md_with_proto_keys_to_md_with_real_keys()
        self.get_html_with_segments()
        return self.segmented_html

    def convert_plain_md_to_md_with_proto_keys(self) -> str:
        self.md_with_proto_keys = self.add_proto_keys_to_md(self.plain_md_src, prefix=self.proto_key_prefix)

    def add_proto_keys_to_md(
        self, md_src: str, prefix: str = "k", early_placeholder_replacement: bool = False
    ):
        """

        :param md_src:      original markdown source
        :param prefix:      prefix for the inserted proto-keys (like "k"→"::k")
        :param early_placeholder_replacement:
                            default: False; if True code-block-placeholders are replaced by the associated
                            content
        """

        # first conversion from md to html (to add proto keys); will be converted back later

        # Convert triple backtick code blocks to HTML before markdown processing
        # also replace its content by placeholder-strings
        md_src_processed = self.convert_triple_backticks_to_html(md_src)

        md = markdown.Markdown()
        html_src = md.convert(md_src_processed)
        pka = ProtoKeyAdder(html_src, prefix=prefix)
        html_src2 = pka.add_proto_keys_to_html()

        # now convert back from html to markdown
        if early_placeholder_replacement:
            self._early_placeholder_replacement = True
        res = self.markdownify_and_postprocess(html_src2)
        return res

    def markdownify_and_postprocess(self, html_src):
        """
        employ customized MarkdownConverter
        """

        mdc = mdf.MarkdownConverter(heading_style="ATX", bullets="-")

        # explicitly define conversion for strong and emphasized text
        mdc.convert_b = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "**"), mdc)
        mdc.convert_em = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "_"), mdc)

        # custom conversion for triple backtick code blocks
        def convert_code_triple_backticks(unused_mdc_self, el, text, convert_as_inline):
            if el.get('class') and 'triple_backticks' in el.get('class'):
                # Convert to triple backtick fenced code block

                # placeholder-replacements will be performed later in span-Adder

                if self._early_placeholder_replacement:
                    # used in some unittests only
                    code_content = self._code_element_contents.get(text, text)
                    return f"\n```{code_content}```"
                else:
                    return f"\n```{text}```"
            else:
                # Use default inline code conversion
                return f"`{text}`"

        mdc.convert_code = types.MethodType(convert_code_triple_backticks, mdc)

        res0 = mdc.convert(html_src)
        res1 = convert_tabs_to_spaces(res0)

        return res1

    def convert_triple_backticks_to_html(self, md_src):
        """
        Convert triple backtick code blocks to HTML code blocks with class="triple_backticks"
        """
        # Pattern to match triple backtick code blocks
        pattern = r"```(.*?)```"

        def replace_code_block(match):
            code_content = match.group(1)
            # Escape HTML entities in the code content
            # import html
            # escaped_content = html.escape(code_content)

            idx = len(self._code_element_contents)

            key = self._code_placeholder(idx)
            self._code_element_contents[key] = code_content

            return f'<code class="triple_backticks">{key}</code>'

        # Use DOTALL flag to match newlines within the code blocks
        result = re.sub(pattern, replace_code_block, md_src, flags=re.DOTALL)
        return result

    def _code_placeholder(self, idx: int):
        return f"::code_placeholder_{idx}::"

    def convert_md_with_proto_keys_to_md_with_real_keys(self) -> str:
        proto_key = f"::{self.proto_key_prefix}"
        self.md_with_real_keys = KeyAdder(self.md_with_proto_keys).replace_proto_key_by_numbered_key(
            proto_key, self.key_prefix
        )
        return self.md_with_real_keys

    def convert_plain_md_to_md_with_real_keys(self):
        self.convert_plain_md_to_md_with_proto_keys()
        return self.convert_md_with_proto_keys_to_md_with_real_keys()

    def get_keys(self) -> list[str]:

        # use caching because we need this several times in one run
        if self.cached_keys is not None:
            return self.cached_keys

        assert self.md_with_real_keys

        cre = re.compile(r"::XXX\d+".replace("XXX", self.key_prefix))
        # matches = list(cre.finditer(self.md_with_real_keys))
        matches = list(cre.findall(self.md_with_real_keys))

        self.cached_keys = matches
        return matches

    def get_html_with_segments(self) -> str:
        """
        Convert markdown to html
        insert spans related to keys
        """

        # this is the second (and final) conversion from md to html
        md = markdown.Markdown()

        # only here we should resolve placeholders
        html_src = md.convert(self.md_with_real_keys)

        if len(html_src) > 0:
            sa = SpanAdder(
                parent_mdp=self,
                html_src=html_src,
                key_prefix=f"::{self.key_prefix}",
                contribution_childs=self.contribution_childs,
            )

            res: str = sa.add_spans_for_keys(prettify=True)
        else:
            res = ""

        self.segmented_html = res
        return self.segmented_html


def _convert_plain_md_to_segmented_html(md_src: str, key_prefix="k") -> str:
    """
    convenience function for unittests not meant (anymore) as public interface function
    """

    mdp = MDProcessor(md_src)
    mdp.convert()

    return mdp.md_with_real_keys, mdp.segmented_html


key_regex = re.compile(r"[ab]\d+")


def decompose_key(key):
    """
    :param key:     str like "a4b12a2b"
    """
    # to match the parts with an easy regex we append a digit and remove it later
    parts = key_regex.findall(f"{key}0")

    if parts:
        # remove the trailing 0 from last part
        assert parts[-1][-1] == "0"
        parts[-1] = parts[-1][:-1]

    return parts


def is_valid_key(key):
    parts = decompose_key(key)
    return "".join(parts) == key


def get_base_name(fpath):
    fname = os.path.split(fpath)[1]
    base_name = os.path.splitext(fname)[0]
    return base_name


def is_valid_fpath(fpath):
    return is_valid_key(get_base_name(fpath))


class DBContribution:
    """
    Represents a contribution wich is not yet stored in a file but comes from the database
    of the web app.
    """

    def __init__(self, ctb_key: str, body: str):
        self.ctb_key = ctb_key
        self.body = body

        # will be set during commit process
        self.fpath: str = None
        self.author_role: str = None


class DebateDirLoader:

    def __init__(self, dirpath, new_debate: bool = False, debate_key: str = None):
        self.dirpath = dirpath
        self.new_debate = new_debate
        self.dir_a = pjoin(self.dirpath, "a")
        self.dir_b = pjoin(self.dirpath, "b")
        self.root_file = pjoin(self.dir_a, "a.md")
        self.num_contributions = None
        self.all_files: list = None

        self.root_mdp: MDProcessor = None
        self.tree: dict[str, MDProcessor] = {}

        # store something like {0: ["a"], 1: ["a1b", "a5b"], 2: ["a5b3a"]}
        self.level_tree: dict[str, list[str]] = None
        # -> deepest_level = len(level_tree) - 1 (deepest_level == 2 for above example)

        self.final_html: str = None

        if debate_key is None:
            raise NotImplementedError
        # TODO: read this from metadata.toml or ensure consistency
        self.debate_key = debate_key

    def load_dir(self, ctb_list: list[DBContribution] = None):
        """

        :param ctb_list:    list of contributions from the database (not repo)
                            background: temporary contributions, not yet committed
        """

        a_files = glob.glob(pjoin(self.dir_a, "*.md"))
        b_files = glob.glob(pjoin(self.dir_b, "*.md"))

        self.all_files = [fpath for fpath in a_files + b_files if is_valid_fpath(fpath)]
        self.all_files.sort()

        for fpath in self.all_files:
            base_name = get_base_name(fpath)

            with open(fpath, "r") as fp:
                md_with_real_keys = fp.read()
            mdp = MDProcessor(key_prefix=base_name, md_with_real_keys=md_with_real_keys, db_ctb=False)
            if len(mdp.get_keys()) == 0:
                fname = os.path.split(fpath)[1]
                msg = (
                    f"Unexpectedly the file '{fname}' of debate '{self.debate_key}' does not contain "
                    "a single key"
                )
                raise ValueError(msg)

            self.tree[base_name] = mdp

        self.process_ctb_list(ctb_list)
        self.handle_root_mdp()
        self.set_level_tree()

    def handle_root_mdp(self):
        self.root_mdp = self.tree["a"]
        self.root_mdp.is_root_mdp = True
        self.root_mdp.debate_key = self.debate_key
        self.num_answers = len(self.tree) - 1  # don't count root contribution als answer

        if self.root_mdp.additional_css_classes:
            additional_class_str = " ".join(self.root_mdp.additional_css_classes)

    # TODO unit-test
    def set_level_tree(self):
        level_tree = collections.defaultdict(list)

        for key in self.tree.keys():
            level = len(decompose_key(key)) - 1
            level_tree[level].append(key)

        self.level_tree = dict(level_tree)

    def process_ctb_list(self, ctb_list: list[DBContribution]):
        """
        Insert those contents which come from the database of the web app (not from repo)
        """
        if ctb_list is None:
            return

        for ctb in ctb_list:
            if ctb.body == "":
                msg = (
                    f"Unexpectedly received empty body for contribution {ctb.ctb_key}. "
                    "-> Contribution ignored."
                )
                logger.warning(msg)
                continue
            mdp = MDProcessor(key_prefix=ctb.ctb_key, plain_md=ctb.body, db_ctb=True)
            mdp.additional_css_classes.append("db_ctb")
            mdp.add_plain_md_as_data = True
            mdp.convert_plain_md_to_md_with_real_keys()
            self.tree[ctb.ctb_key] = mdp

    def generate_html_with_contributions(self, parent_mdp: MDProcessor = None):
        if parent_mdp is None:
            parent_mdp = self.root_mdp

        next_turn_key = get_next_turn_key(parent_mdp.key_prefix)

        # get all keys which are used in this statement block (without contributions)
        key_str_list = parent_mdp.get_keys()

        # recursively process elements
        for key_str in key_str_list:
            key = key_str.lstrip("::")

            contribution_key = f"{key}{next_turn_key}"
            if contribution_key in self.tree:
                child_mdp = self.tree.get(contribution_key)

                # this recursively creates the .segmented_html
                # attributes of the child_mdp objects
                self.generate_html_with_contributions(parent_mdp=child_mdp)
                parent_mdp.contribution_childs[key] = child_mdp

        # this calls SpanAdder.add_spans_for_keys()
        res_segmented_html: str = parent_mdp.get_html_with_segments()
        if parent_mdp == self.root_mdp:
            self.final_html = res_segmented_html


def get_contribution_key(segment_key):
    """
    For a keys like "a5", "a304b1" generate "a3b" or "a304b1a"
    """
    next_turn_key = get_next_turn_key(segment_key)
    return f"{segment_key}{next_turn_key}"


def get_next_turn_key(segment_key):
    """
    For a keys like "a5", "a304b1" generate "b" or "a"
    (opposite of the letter of the last part)
    """
    key_parts = decompose_key(segment_key)
    last_part_letter = key_parts[-1][0]
    assert last_part_letter in ("a", "b")
    next_turn_key = {"a": "b", "b": "a"}[last_part_letter]
    return next_turn_key


def load_dir(
    dirpath, ctb_list: list[DBContribution] = None, new_debate: bool = False, debate_key: str = None
) -> DebateDirLoader:

    ddl = DebateDirLoader(dirpath=dirpath, new_debate=new_debate, debate_key=debate_key)
    ddl.load_dir(ctb_list=ctb_list)
    ddl.generate_html_with_contributions()

    return ddl

class RepoNotFoundError(Exception):
    pass


def load_repo(
    repo_host_dir: str, debate_key: str, ctb_list: list[DBContribution] = None, new_debate: bool = True
) -> DebateDirLoader:

    repo_dir = pjoin(repo_host_dir, debate_key)

    if new_debate:
        return load_dir(repo_dir, ctb_list, new_debate, debate_key=debate_key)

    if not os.path.isdir(repo_dir):
        raise FileNotFoundError(f"directory: {repo_dir}")
    if not os.path.isdir(pjoin(repo_dir, ".git")):

        part_list = repo_dir.split(os.path.sep)
        display_dir = os.path.sep.join(part_list[-3:])
        raise RepoNotFoundError(f"directory: {display_dir}/.git")

    return load_dir(repo_dir, ctb_list, debate_key=debate_key)


def commit_ctb_list(repo_host_dir: str, debate_key: str, ctb_list: list[DBContribution]):

    repo_dir = pjoin(repo_host_dir, debate_key)
    repo = git.Repo(repo_dir)

    if not os.path.isdir(repo_dir):
        msg = f"Directory could not be found: {repo_dir}"
        raise FileNotFoundError(msg)

    rel_paths = []
    for ctb in ctb_list:
        write_ctb_to_file(repo_dir, ctb)

        repo.index.add(ctb.fpath)
        rel_paths.append(ctb.fpath.replace(repo_dir, "")[1:])

    if len(ctb_list) == 1:
        msg = f"add contribution {rel_paths[0]}"
    else:
        contributions = "\n".join(rel_paths)
        msg = f"add contributions:\n{contributions}"

    author = repo_handling.get_author(debate_key, ctb.author_role)
    repo.index.commit(message=msg, author=author)


def write_ctb_to_file(repo_dir: str, ctb: DBContribution):

    ctb.author_role = ctb.ctb_key[-1]
    assert ctb.author_role in ["a", "b"]

    dir_path = pjoin(repo_dir, ctb.author_role)
    os.makedirs(dir_path, exist_ok=True)
    ctb.fpath = pjoin(dir_path, f"{ctb.ctb_key}.md")

    if os.path.exists(ctb.fpath):
        msg = f"File unexpectedly already exists: {ctb.fpath}"
        raise FileExistsError(msg)

    mdp = MDProcessor(key_prefix=ctb.ctb_key, plain_md=ctb.body)
    mdp._early_placeholder_replacement = True
    md_with_real_keys = mdp.convert_plain_md_to_md_with_real_keys()
    with open(ctb.fpath, "w") as fp:
        fp.write(md_with_real_keys)


def commit_ctb(repo_host_dir: str, debate_key: str, ctb: DBContribution):

    ctb_list = [ctb]
    commit_ctb_list(repo_host_dir, debate_key, ctb_list)


def unpack_repos(target_dir):
    """
    Unpack predefined fixture repos
    """
    target_dir = os.path.abspath(target_dir)
    from . import repo_handling, fixtures

    repo_dirs = os.listdir(fixtures.TEST_REPO_HOST_DIR)
    repo_dirs.sort()
    for repo_dir_name in repo_dirs:
        repo_dir_path = pjoin(fixtures.TEST_REPO_HOST_DIR, repo_dir_name)
        repo_workdir = pjoin(target_dir, repo_dir_name)
        utils.tolerant_rmtree(repo_workdir)
        patch_dir = pjoin(repo_dir_path, "patches_01")
        repo_handling.rollout_patches(repo_dir=repo_workdir, patch_dir=patch_dir)


def process_content_dir(content_dir:str, target_dir:str, convert_to_patches=False):

    from . import fixtures
    content_dir1 = content_dir.replace("__FIXTURES_RP__", fixtures.rp_path)

    content_dir1 = os.path.abspath(content_dir1)
    target_dir = os.path.abspath(target_dir)

    fpaths = glob.glob(pjoin(content_dir1, "*", "*.md"))
    fpaths.sort()

    result_files = []

    for src_fpath in fpaths:
        _, fname = os.path.split(src_fpath)
        target_fpath = src_fpath.replace(content_dir1, target_dir)
        target_dirpath, _ = os.path.split(target_fpath)
        os.makedirs(target_dirpath, exist_ok=True)
        basename, _  = os.path.splitext(fname)
        add_keys_to_plain_md_file(src_fpath=src_fpath, target_fpath=target_fpath, key_prefix=basename)
        result_files.append(target_fpath)
        print(f"File written: {target_fpath}")

    if convert_to_patches:
        convert_dir_to_collection_of_patches(target_dir=target_dir)

    return result_files


def add_keys_to_plain_md_file(src_fpath: str, target_fpath: str, key_prefix: str):

    with open(src_fpath) as fp:
        md_src = fp.read()

    mdp = MDProcessor(plain_md=md_src, key_prefix=key_prefix)

    mdp.convert_plain_md_to_md_with_proto_keys()
    mdp.convert_md_with_proto_keys_to_md_with_real_keys()

    with open(target_fpath, "w") as fp:
        fp.write(mdp.md_with_real_keys)


def get_basename(fpath):
    dir_path, fname = os.path.split(fpath)
    basename, ext = os.path.splitext(fname)
    return basename

@utils.preserve_cwd
def convert_dir_to_collection_of_patches(target_dir):

    os.chdir(target_dir)
    commits = collections.defaultdict(list)

    fpaths = glob.glob("*/*.md")
    fpaths.sort()

    for fpath in fpaths:
        key = get_base_name(fpath)
        level = len(decompose_key(key)) - 1
        commits[level].append(fpath)

    commits = dict(sorted(commits.items()))

    utils.tolerant_rmtree("./git")
    os.system("git init")

    users = ["user_a <user_a@example.org>", "user_b <user_b@example.org>"]

    for level, files in commits.items():
        for fpath in files:
            os.system(f"git add {fpath}")
        user = users[level % 2]
        os.system(f'git commit --author="{user}" -m "automatic contribution"')

    os.system("git format-patch --root -o patches_01")


def main():
    pass
