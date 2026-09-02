import re
import os
import glob
import json
import logging
import collections
import subprocess
from datetime import datetime, timezone

import yaml
from bs4 import BeautifulSoup, element
import git

from ipydex import IPS

from . import utils
from . import repo_handling
from . import references
from .key_management import (
    DEFAULT_SPLITTER_SYNTAX_VERSION,
    SPLITTER_SYNTAX_VERSION,
    ProtoKeyAdder,
    strip_force_split_markers,
)
from .md_handling import MDHandler, KeyAdder, convert_tabs_to_spaces  # noqa: F401 (re-exported)
from .references import (  # noqa: F401 (re-exported)
    key_regex,
    decompose_key,
    is_valid_key,
    parse_key_unit,
    get_anchor_segment_key,
    get_first_referenced_segment_key,
    get_parent_contribution_key,
    get_segment_source,
    get_segment_words,
    validate_reference,
)

pjoin = os.path.join

TEST_DEBATE_KEY = "d1-lorem_ipsum"

# this should be the same as in the web-application
logger = logging.getLogger("fair-debate")
logger.debug("fair_debate_md.core loaded")


class SpanAdder:
    def __init__(
        self, parent_mdp, html_src: str, key_prefix: str, contribution_childs: dict[str, list["MDProcessor"]] = None
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
        for key, mdp_list in self.contribution_childs.items():
            if not mdp_list:
                continue

            referenced_segment = segment_dict.get(key)
            if referenced_segment is None:
                ctb_keys = [mdp.key_prefix for mdp in mdp_list]
                msg = f"anchor segment '{key}' (referenced by {ctb_keys}) not found among the segments"
                raise ValueError(msg)
            segment_parent = referenced_segment.parent

            if segment_parent.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                # special treatment of answer-contributions to headings (styling reasons)
                wrapper_div = self.soup.new_tag("div", attrs={"class": "answered_heading"})
                segment_parent.insert_after(wrapper_div)
                segment_parent.extract()
                wrapper_div.append(segment_parent)
                class_list = segment_parent.attrs.get("class", "").split(" ")
                class_list.append("heading")
                segment_parent.attrs["class"] = " ".join(class_list).strip()
                insert_after_target = segment_parent
            else:
                insert_after_target = referenced_segment

            # Insert in reverse order so that visual order matches the sorted mdp_list
            # (each insert_after pushes the new div right after the anchor)
            for mdp in reversed(mdp_list):
                contribution_content = mdp.get_html_with_segments()
                contribution_soup = BeautifulSoup(contribution_content, "html.parser")
                # here the use of `level` is consistent with the web app:
                # current level (e.g. 1 (= number of key-parts) is applied to contribution_soup)
                self._replace_p_with_div(contribution_soup, self.level)
                additional_class_str = " ".join(mdp.additional_css_classes)
                class_str = f"contribution level{self.level} {additional_class_str}".strip()

                attribute_dict = {"class": class_str, "id": f"contribution_{mdp.key_prefix}"}
                self._add_reference_data_attributes(attribute_dict, mdp.key_prefix)
                if mdp.add_plain_md_as_data:
                    # Note this attribute must be allowed by bleach (in settings.py of the web app)
                    attribute_dict["data-plain_md_src"] = json.dumps(mdp.plain_md_src)

                contribution_div = self.soup.new_tag("div", attrs=attribute_dict)
                contribution_div.extend(contribution_soup)
                insert_after_target.insert_after(contribution_div)

    @staticmethod
    def _add_reference_data_attributes(attribute_dict: dict, ctb_key: str) -> None:
        """
        For contributions with a range or word reference add data attributes
        which allow the frontend to render the reference without re-parsing
        the key. Plain references get no extra attributes.
        """
        parts = references.decompose_key(ctb_key)
        if len(parts) < 2:
            return
        try:
            ref_unit = references.parse_key_unit(parts[-2])
        except ValueError:
            return
        if not (ref_unit.is_segment_range or ref_unit.has_word_ref):
            return

        # Note: these attributes must be allowed by bleach (settings.py of the web app)
        attribute_dict["data-ref-anchor"] = references.get_anchor_segment_key(ctb_key)
        if ref_unit.is_segment_range:
            attribute_dict["data-ref-seg-start"] = references.get_first_referenced_segment_key(ctb_key)
        if ref_unit.has_word_ref:
            if ref_unit.word_end is not None:
                attribute_dict["data-ref-words"] = f"{ref_unit.word_start}-{ref_unit.word_end}"
            else:
                attribute_dict["data-ref-words"] = str(ref_unit.word_start)

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


class MDProcessor(MDHandler):

    def __init__(
        self,
        plain_md: str = None,
        proto_key_prefix="k",
        key_prefix="a",
        md_with_real_keys: str = None,
        # store whether this is a data-base contribution (i.e. not yet committed)
        db_ctb: bool = None,
        convert_now=False,
        splitter_version: int = None,
    ):
        super().__init__(
            plain_md=plain_md,
            proto_key_prefix=proto_key_prefix,
            key_prefix=key_prefix,
            md_with_real_keys=md_with_real_keys,
            db_ctb=db_ctb,
            splitter_version=splitter_version,
        )

        # html/segment/contribution related state
        self.segmented_html: str = None
        self.contribution_childs: dict[str, list[MDProcessor]] = collections.defaultdict(list)
        self.is_root_mdp: bool = False
        self.debate_key: str = None

        # front-matter / ordering metadata (Phase 4 foundation)
        self.front_matter: dict = {}
        self.created: str | None = None
        self.order_hint = None

        # convenience: save one line in the caller
        if convert_now:
            self.convert()

    def convert(self) -> str:
        self.convert_plain_md_to_md_with_proto_keys()
        self.convert_md_with_proto_keys_to_md_with_real_keys()
        self.get_html_with_segments()
        return self.segmented_html

    def get_html_with_segments(self) -> str:
        """
        Convert markdown to html
        insert spans related to keys
        """

        # this is the second (and final) conversion from md to html
        # only here we should resolve placeholders
        html_src = self._md_to_html(self.md_with_real_keys)

        # The force-split markers have done their work when the `::aN` keys were
        # materialized; they stay in the stored `.md` (see `FORCE_SPLIT_MARKER`) but must
        # not reach the reader. Removing them here and not earlier is what keeps them in
        # the repo. Code blocks are placeholders at this point and are restored further
        # down in `SpanAdder.convert_code_placeholders`, so their content is untouched.
        html_src = strip_force_split_markers(html_src)

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


def get_base_name(fpath):
    fname = os.path.split(fpath)[1]
    base_name = os.path.splitext(fname)[0]
    return base_name


def is_valid_fpath(fpath):
    return is_valid_key(get_base_name(fpath))


def _git_first_commit_iso(fpath: str) -> str | None:
    """
    Return the ISO-8601 timestamp of the first commit that added `fpath`
    (using --diff-filter=A --follow). Returns None on any failure.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--diff-filter=A", "--follow", "--format=%aI", "--", fpath],
            cwd=os.path.dirname(fpath) or ".",
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    if not out:
        return None
    return out.splitlines()[-1]


def split_front_matter(text: str) -> tuple[dict, str]:
    """
    Split a YAML front-matter header from the body.

    Returns (front_matter_dict, body). If no header is present, returns ({}, text).
    """
    if not text.startswith("---\n"):
        return {}, text

    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        return {}, text

    header_src = text[4:end_idx]
    body = text[end_idx + len("\n---\n"):]
    try:
        data = yaml.safe_load(header_src)
    except yaml.YAMLError:
        return {}, text
    if not isinstance(data, dict):
        return {}, text
    return data, body


def build_front_matter(**fields) -> str:
    """
    The yaml header a contribution file carries, or "" when there is nothing to record.

    The counterpart of `split_front_matter()`, and the one place that decides how the
    header is spelled -- it is written from two places (a live publication and the fixture
    builder) which must produce byte-identical files for identical content.
    """
    if not fields:
        return ""
    return "---\n" + yaml.safe_dump(fields, sort_keys=False, allow_unicode=True) + "---\n"


class DBContribution:
    """
    Represents a contribution wich is not yet stored in a file but comes from the database
    of the web app.
    """

    def __init__(self, ctb_key: str, body: str, order_hint=None):
        self.ctb_key = ctb_key
        self.body = body
        self.order_hint = order_hint

        # will be set during commit process
        self.fpath: str = None
        self.author_role: str = None


class DebateDirLoader:

    def __init__(self, dirpath, new_debate: bool = False, debate_key: str = None):
        self.dirpath = dirpath
        self.new_debate = new_debate
        self.dir_a = pjoin(self.dirpath, "a")
        self.root_file = pjoin(self.dir_a, "a.md")
        self.num_contributions = None
        self.all_files: list = None

        self.root_mdp: MDProcessor = None
        self.tree: dict[str, MDProcessor] = {}

        # store something like {0: ["a"], 1: ["a1b", "a5b"], 2: ["a5b3a"]}
        self.level_tree: dict[str, list[str]] = None
        # -> deepest_level = len(level_tree) - 1 (deepest_level == 2 for above example)

        self.final_html: str = None

        # dict[str, list[int]]: segment key -> flat [start0, end0, start1, end1, ...]
        # char-offset pairs, one pair per raw word (see `_compute_word_offsets`
        # docstring for the full contract). Populated after `final_html` is
        # assembled, i.e. after `generate_html_with_contributions()`.
        self.word_offsets: dict[str, list[int]] = {}

        if debate_key is None:
            raise NotImplementedError
        # TODO: read this from metadata.toml or ensure consistency
        self.debate_key = debate_key

    def load_dir(self, ctb_list: list[DBContribution] = None):
        """

        :param ctb_list:    list of contributions from the database (not repo)
                            background: temporary contributions, not yet committed
        """

        all_md_files = glob.glob(pjoin(self.dirpath, "*", "*.md"))
        self.all_files = []
        for fpath in all_md_files:
            dir_name = os.path.basename(os.path.dirname(fpath))
            if re.match(r"^[a-z]+$", dir_name) and is_valid_fpath(fpath):
                self.all_files.append(fpath)
        self.all_files.sort()

        for fpath in self.all_files:
            base_name = get_base_name(fpath)

            with open(fpath, "r") as fp:
                file_content = fp.read()
            front_matter, md_with_real_keys = split_front_matter(file_content)
            # absent means the file predates the field, and everything written before it
            # came from ruleset 1 -- so the default is a statement about history, not a
            # fallback for a missing value
            mdp = MDProcessor(
                key_prefix=base_name,
                md_with_real_keys=md_with_real_keys,
                db_ctb=False,
                splitter_version=front_matter.get("splitter_version", DEFAULT_SPLITTER_SYNTAX_VERSION),
            )
            mdp.front_matter = front_matter
            mdp.created = front_matter.get("created")
            if mdp.created is None:
                mdp.created = _git_first_commit_iso(fpath)
            mdp.order_hint = mdp.created
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
        self.validate_references()

    def handle_root_mdp(self):
        self.root_mdp = self.tree["a"]
        self.root_mdp.is_root_mdp = True
        self.root_mdp.debate_key = self.debate_key
        self.num_answers = len(self.tree) - 1  # don't count root contribution als answer

        if self.root_mdp.additional_css_classes:
            additional_class_str = " ".join(self.root_mdp.additional_css_classes)

    def validate_references(self):
        """
        Validate range and word references against their parent contribution.

        Contributions with plain references keep the legacy behavior (missing
        parents/segments are silently ignored). For range/word references a
        missing parent or an inconsistent reference raises ValueError.
        """
        for ctb_key, mdp in self.tree.items():
            parts = references.decompose_key(ctb_key)
            if len(parts) < 2:
                continue
            try:
                ref_unit = references.parse_key_unit(parts[-2])
            except ValueError:
                continue
            if not (ref_unit.is_segment_range or ref_unit.has_word_ref):
                continue

            parent_key = references.get_parent_contribution_key(ctb_key)
            parent_mdp = self.tree.get(parent_key)
            if parent_mdp is None:
                msg = (
                    f"invalid reference '{ctb_key}' in debate '{self.debate_key}': parent "
                    f"contribution '{parent_key}' does not exist"
                )
                raise ValueError(msg)
            references.validate_reference(
                ctb_key, parent_mdp.md_with_real_keys, code_contents=parent_mdp._code_element_contents
            )

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
            mdp.front_matter = {}
            mdp.order_hint = ctb.order_hint
            mdp.convert_plain_md_to_md_with_real_keys()
            self.tree[ctb.ctb_key] = mdp

    def generate_html_with_contributions(self, parent_mdp: MDProcessor = None):
        if parent_mdp is None:
            parent_mdp = self.root_mdp

        # Clear to avoid duplication on repeated calls
        parent_mdp.contribution_childs.clear()

        # get all keys which are used in this statement block (without contributions)
        key_str_list = parent_mdp.get_keys()

        # map each contribution key to the segment it is anchored at
        # (plain reference: the referenced segment; range/word reference: see
        # references.get_anchor_segment_key)
        anchor_map = {k: references.get_anchor_segment_key(k) for k in self.tree}

        # recursively process elements
        for key_str in key_str_list:
            key = key_str.lstrip("::")

            # Find all direct children: tree keys anchored at this segment
            candidate_keys = [k for k, anchor in anchor_map.items() if anchor == key]
            child_keys = sorted(candidate_keys, key=lambda k: _sort_key(self.tree[k]))

            for child_key in child_keys:
                child_mdp = self.tree[child_key]
                # this recursively creates the .segmented_html
                # attributes of the child_mdp objects
                self.generate_html_with_contributions(parent_mdp=child_mdp)
                parent_mdp.contribution_childs[key].append(child_mdp)

        # this calls SpanAdder.add_spans_for_keys()
        res_segmented_html: str = parent_mdp.get_html_with_segments()
        if parent_mdp == self.root_mdp:
            self.final_html = res_segmented_html
            self._compute_word_offsets()

    def _compute_word_offsets(self) -> None:
        """
        Populate `self.word_offsets` for every segment of every contribution
        in the debate.

        Coordinate system (the critical contract, see also T2 report): each
        offset pair indexes into the segment's `.get_text()` as extracted
        from `self.final_html` -- i.e. the *actually delivered* HTML, after
        `SpanAdder.add_spans_for_keys(prettify=True)`. This is, by construction,
        the same string a browser exposes as
        `document.getElementById(segment_key).textContent`, regardless of
        what prettify() does to whitespace: we never assume a coordinate
        system, we parse the delivered string itself.

        Raw words come exclusively from `references.get_segment_words()`
        (the frozen tokenizer spec), looked up against the `md_with_real_keys`
        of the contribution that owns the segment (found via
        `MDHandler.get_keys()`, not by string-splitting the segment key).
        """
        self.word_offsets = {}

        owner_by_segment_key: dict[str, MDProcessor] = {}
        for mdp in self.tree.values():
            for raw_key in mdp.get_keys():
                owner_by_segment_key[raw_key.lstrip(":")] = mdp

        soup = BeautifulSoup(self.final_html, "html.parser")
        for span in soup.find_all("span", class_="segment"):
            segment_key = span.attrs["id"]
            owner_mdp = owner_by_segment_key[segment_key]
            words = references.get_segment_words(owner_mdp.md_with_real_keys, segment_key)
            segment_text = span.get_text()
            self.word_offsets[segment_key] = references.get_rendered_word_offsets(segment_text, words)


def get_contribution_key(segment_key, answering_token):
    """
    For a segment key like "a5" and answering_token "c" generate "a5c".
    Example: get_contribution_key('a5', 'c') == 'a5c'
             get_contribution_key('a304b1', 'a') == 'a304b1a'
    """
    return f"{segment_key}{answering_token}"


def get_last_token(key):
    """
    Return the last letter-run (token) at the end of a key string.
    Example: get_last_token('a5c3b') == 'b'
             get_last_token('a3ab') == 'ab'
    """
    m = re.search(r"[a-z]+$", key)
    return m.group() if m else None


def _sort_key(mdp):
    """
    Sort key for sibling contributions: primary by order_hint (None last),
    secondary lex. by role-token (last letter-run of ctb_key / key_prefix).
    """
    oh = mdp.order_hint
    key = getattr(mdp, "ctb_key", None) or getattr(mdp, "key_prefix", "")
    return (oh is None, oh if oh is not None else "", get_last_token(key) or "")



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


def commit_ctb_list(repo_host_dir: str, debate_key: str, ctb_list: list[DBContribution]) -> str:
    """
    Write the given contributions to the repo and commit them.

    :return:    the hex sha of the created commit

    Note that *all* contributions of one call end up in *one* commit and thus share the
    same hash. That is intended (they are published in one action), but it means the hash
    does not identify a single contribution -- see `contribution_commit_hashes`.
    """

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
    commit_sha = repo_handling.commit_index(repo, repo_dir, msg, author)

    # keep the repo cloneable over HTTP; a stale server info would make a clone deliver an
    # older state without saying so
    repo_handling.prepare_repo_for_serving(repo_dir)

    return commit_sha


def write_ctb_to_file(repo_dir: str, ctb: DBContribution):

    ctb.author_role = get_last_token(ctb.ctb_key)

    dir_path = pjoin(repo_dir, ctb.author_role)
    os.makedirs(dir_path, exist_ok=True)
    ctb.fpath = pjoin(dir_path, f"{ctb.ctb_key}.md")

    if os.path.exists(ctb.fpath):
        msg = f"File unexpectedly already exists: {ctb.fpath}"
        raise FileExistsError(msg)

    mdp = MDProcessor(key_prefix=ctb.ctb_key, plain_md=ctb.body)
    mdp._early_placeholder_replacement = True
    md_with_real_keys = mdp.convert_plain_md_to_md_with_real_keys()

    # `splitter_version` says which segmentation ruleset produced the `::aN` markers just
    # written into the body. It has to travel with the file rather than sit in a database
    # column: the repo is handed out on its own, and whoever renders it later needs to
    # know which rules to apply -- segment keys are the prefix of every answer key, so
    # re-segmenting under changed rules breaks every reference into this contribution.
    header = build_front_matter(
        created=datetime.now(timezone.utc).isoformat(),
        splitter_version=SPLITTER_SYNTAX_VERSION,
    )
    with open(ctb.fpath, "w") as fp:
        fp.write(header)
        fp.write(md_with_real_keys)


def commit_ctb(repo_host_dir: str, debate_key: str, ctb: DBContribution) -> str:
    """
    Write a single contribution to the repo and commit it.

    :return:    the hex sha of the created commit
    """

    ctb_list = [ctb]
    return commit_ctb_list(repo_host_dir, debate_key, ctb_list)


# a contribution file lives at "<role_token>/<contribution_key>.md" inside a debate repo
_ctb_rel_path_regex = re.compile(r"^([a-z]+)/([a-z0-9]+)\.md$")
_git_log_header_regex = re.compile(r"^([0-9a-f]{40})\t(.+)$")


def _read_git_log(repo_dir: str, with_signature_status: bool = False) -> list[tuple]:
    """
    The repo's commits, newest first, as (hash, author date ISO-8601, changed paths) --
    plus git's one-letter signature status as a fourth field when asked for.

    :return:    list of tuples; empty on any failure (no git repo, git not installed,
                unreadable repo)

    One `git log` for the whole repo rather than one call per file (as
    `_git_first_commit_iso` does): both callers below want the complete picture anyway,
    and the per-file variant costs one subprocess each.

    `with_signature_status` is off by default because verifying costs a signature check
    per commit, and only the integrity page displays it. It verifies against the repo's
    own `allowed_signers`, which is what a reader who clones will use as well -- but note
    that the server is then checking a signature against a file it wrote itself. That says
    the signature is intact, not that the key is trustworthy; the latter can only be
    settled outside this server.

    Merge commits arrive with an empty path list (`--name-only` does not walk into them).
    Content repos are written by a single process and are linear, so there are none.
    """

    if not os.path.isdir(pjoin(repo_dir, ".git")):
        return []

    log_format = "%H%x09%aI"
    config_args = []
    if with_signature_status:
        log_format += "%x09%G?"
        config_args = [
            "-c",
            f"gpg.ssh.allowedSignersFile={pjoin(repo_dir, repo_handling.ALLOWED_SIGNERS_FILENAME)}",
        ]

    try:
        result = subprocess.run(
            # the tab separator cannot occur in any field, so the header line is
            # unambiguous even next to a path
            ["git", *config_args, "log", f"--format={log_format}", "--name-only"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    commits = []
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if not line:
            continue
        match = _git_log_header_regex.match(line)
        if match is not None:
            fields = match.group(2).split("\t")
            timestamp = fields[0]
            status = fields[1] if len(fields) > 1 else ""
            commits.append((match.group(1), timestamp, [], status))
        elif commits:
            commits[-1][2].append(line)

    return commits


def contribution_commit_hashes(repo_host_dir: str, debate_key: str) -> dict[str, str]:
    """
    Map every contribution key of a debate repo to the hash of the commit that
    *last touched* its file.

    :return:    dict {contribution_key: commit_hash}; empty on any failure

    Why the last touching commit and not the one that introduced the file: the purpose of
    the hash is to make a change to a published contribution detectable (see
    `konzept_manipulationssicherheit.md` in the web repo, E1). For an untouched file both
    are the same commit; they only differ once the file *was* changed -- and exactly then
    the introducing commit would keep displaying an unchanged hash, i.e. hide what it is
    supposed to reveal. A commit hash covers the whole history leading up to it, so a
    rewrite of any earlier commit changes it too.
    """

    repo_dir = pjoin(repo_host_dir, debate_key)

    hashes = {}
    # newest commit first -> the first mention of a path is its most recent change
    for commit_hash, _, rel_paths, _status in _read_git_log(repo_dir):
        for rel_path in rel_paths:
            match = _ctb_rel_path_regex.match(rel_path)
            if match is None:
                # repo-level files (README.md, data.toml, ...) and anything not shaped
                # like a contribution are none of this function's business
                continue
            ctb_key = match.group(2)
            if ctb_key in hashes:
                continue
            if not os.path.isfile(pjoin(repo_dir, rel_path)):
                # the file was deleted later; there is nothing left to label with it
                continue
            hashes[ctb_key] = commit_hash

    return hashes


def debate_commit_log(
    repo_host_dir: str, debate_key: str, with_signature_status: bool = False
) -> list[dict]:
    """
    The commit chain of a debate repo, newest first, for display.

    :return:    list of {"hash", "timestamp", "contribution_keys", "signature"};
                empty on any failure

    `contribution_keys` names the contributions a commit touched, in the order git
    reports them. Unlike `contribution_commit_hashes` this does NOT drop keys whose file
    was later deleted: the chain is meant to show what happened, and a removal is part of
    that. Commits that touched no contribution at all (the initial commit with the repo's
    README, for instance) are kept with an empty list -- leaving gaps in a chain that is
    shown as evidence would be the wrong kind of tidiness.
    """

    repo_dir = pjoin(repo_host_dir, debate_key)

    commit_log = []
    for commit_hash, timestamp, rel_paths, signature in _read_git_log(
        repo_dir, with_signature_status=with_signature_status
    ):
        ctb_keys = []
        for rel_path in rel_paths:
            match = _ctb_rel_path_regex.match(rel_path)
            if match is not None:
                ctb_keys.append(match.group(2))
        commit_log.append(
            {
                "hash": commit_hash,
                "timestamp": timestamp,
                "contribution_keys": ctb_keys,
                # git's own one-letter verdict: G good, U untrusted key, N unsigned,
                # B/E/X/Y/R for the various ways a signature can be broken. "" when the
                # status was not requested.
                "signature": signature,
            }
        )

    return commit_log


def debate_bundle(repo_host_dir: str, debate_key: str) -> bytes:
    """
    The complete content repo of a debate -- history included -- as a single git bundle.

    :return:    the bundle as bytes; empty on any failure (no git repo, git not
                installed, a repo without commits)

    A bundle rather than an archive of the working tree: the point of handing the repo
    out is that a reader can check the commit chain against a fingerprint they noted
    earlier, and an archive of the file contents carries no chain at all. `git clone
    <file>` turns a bundle back into a full repo, so the check needs nothing but git.

    Written to git's stdout instead of through a temporary file: the caller wants the
    bytes, and a debate repo is small (kilobytes), so a temp file would only add cleanup
    that can fail.
    """

    repo_dir = pjoin(repo_host_dir, debate_key)

    if not os.path.isdir(pjoin(repo_dir, ".git")):
        return b""

    try:
        result = subprocess.run(
            # `--all` so every ref travels along; content repos have one branch, but a
            # bundle that silently omitted a ref would be the wrong kind of evidence
            ["git", "bundle", "create", "-", "--all"],
            cwd=repo_dir,
            capture_output=True,  # no text=True: a bundle is binary
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return b""

    if result.returncode != 0:
        return b""

    return result.stdout


def unpack_repos(target_dir, demo_only: bool = False):
    """
    Unpack predefined fixture repos.

    :param demo_only:   restrict to `fixtures.DEMO_DEBATE_KEYS` -- what a deployment
                        wants. The default rolls out everything, which is what the test
                        suites need. See the comment on that constant for the reason.
    """
    target_dir = os.path.abspath(target_dir)
    from . import repo_handling, fixtures

    repo_dirs = os.listdir(fixtures.TEST_REPO_HOST_DIR)
    if demo_only:
        repo_dirs = [name for name in repo_dirs if name in fixtures.DEMO_DEBATE_KEYS]
        missing = set(fixtures.DEMO_DEBATE_KEYS) - set(repo_dirs)
        if missing:
            # a typo in the constant would otherwise deploy an instance with less content
            # than intended and say nothing about it
            raise ValueError(f"DEMO_DEBATE_KEYS names debates without a repo: {sorted(missing)}")
    repo_dirs.sort()
    for repo_dir_name in repo_dirs:
        repo_dir_path = pjoin(fixtures.TEST_REPO_HOST_DIR, repo_dir_name)
        repo_workdir = pjoin(target_dir, repo_dir_name)
        utils.tolerant_rmtree(repo_workdir)
        patch_dir = pjoin(repo_dir_path, "patches_01")
        # the key explicitly, not left to the directory name: it goes into the README, and
        # deriving it from the target path would make the same debate come out differently
        # depending on where it was unpacked
        repo_handling.rollout_patches(
            repo_dir=repo_workdir, patch_dir=patch_dir, debate_key=repo_dir_name
        )


def main():
    pass
