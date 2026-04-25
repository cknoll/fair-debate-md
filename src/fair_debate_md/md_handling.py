"""
Markdown handling: everything related to converting plain markdown to
markdown with (proto-)keys.

This module intentionally does NOT contain the html/segment/contribution logic.
The goal is to be able to work on markdown-level key handling independently
from the rest of the code.
"""

import re
import types

import markdown
import markdownify as mdf

from . import utils
from .key_management import ProtoKeyAdder


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


class MDHandler:
    """
    Handles the markdown-level operations: insertion of proto-keys and
    conversion of proto-keys to numbered (real) keys.

    This is a base class for `MDProcessor` (which adds the html/segment logic).
    """

    def __init__(
        self,
        plain_md: str = None,
        proto_key_prefix="k",
        key_prefix="a",
        md_with_real_keys: str = None,
        # store whether this is a data-base contribution (i.e. not yet committed)
        db_ctb: bool = None,
    ):
        self.plain_md_src = plain_md
        self.additional_css_classes = []
        self.add_plain_md_as_data = False

        self.proto_key_prefix = proto_key_prefix
        self.key_prefix = key_prefix

        self.md_with_proto_keys: str = None
        self.md_with_real_keys = md_with_real_keys
        self.db_ctb: bool = db_ctb
        self.cached_keys: list = None

        self._code_element_contents = {}
        self._early_placeholder_replacement = False

        # for debugging we save intermediate html-results
        self.html_results = []

    def _md_to_html(self, md_src: str) -> str:
        """
        Convert markdown to html via `python-markdown`.

        Extensions are currently disabled on purpose. See `TODO-AIDER` below.
        """
        indent_width = utils.detect_list_indent(md_src)
        use_extensions = True
        if use_extensions:
            # AIDER-Info:
            # I want to use these extensions because future markdownify versions change the handling
            # of nested lists and thus specifying the indent-width is necessary then
            # however if I activate them they also change the behavior.

            # TODO-AIDER:
            # my desired solution (steps):
            # - [x] refactor the whole markdown-handling code (especially until proto-keys are added) into a separate module (current tests should pass)
            #   - [x] also refactor the tests `test_010__add_keys_to_md`, `test_030__get_html_with_segments` and `test_031__get_html_with_segments_bug` into a separate module
            #   - [x] the goal is to work on this problem independently from the rest of the code
            # - [x] simplify that code and add more fine-grained tests on intermediate results (but not too many)
            # - [x] activate extension
            # - track down the changed behavior with the more fine-grained tests

            extensions = ["mdx_truly_sane_lists"]
            extension_configs = {"mdx_truly_sane_lists": {"nested_indent": indent_width}}
        else:
            extensions = []
            extension_configs = {}
        md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs,)

        return md.convert(md_src)

    def _preprocess_code_blocks(self, md_src: str) -> str:
        """
        Pipeline step 1: replace triple-backtick code blocks with html
        `<code class="triple_backticks">...</code>` tags containing a
        placeholder. The real content is stored in `self._code_element_contents`
        and re-inserted later (either here or in the span-adder step).
        """
        return self.convert_triple_backticks_to_html(md_src)

    def _add_proto_keys_to_html(self, html_src: str, prefix: str) -> str:
        """
        Pipeline step 3: add proto-keys (e.g. `::k`) to the html source.
        """
        pka = ProtoKeyAdder(html_src, prefix=prefix)
        return pka.add_proto_keys_to_html()

    def _html_to_md_with_proto_keys(self, html_src: str) -> str:
        """
        Pipeline step 4: convert the proto-key-annotated html back to markdown.
        """
        return self.markdownify_and_postprocess(html_src)

    def add_proto_keys_to_md(
        self, md_src: str = None, prefix: str = "k", early_placeholder_replacement: bool = False
    ):
        """
        Add proto-keys to a markdown source via a four-step pipeline:
            1. preprocess code blocks (placeholders)
            2. md → html
            3. add proto-keys to html
            4. html → md

        :param md_src:      original markdown source
        :param prefix:      prefix for the inserted proto-keys (like "k"→"::k")
        :param early_placeholder_replacement:
                            default: False; if True code-block-placeholders are replaced by the associated
                            content
        """

        if md_src is None:
            md_src = self.plain_md_src

        if early_placeholder_replacement:
            self._early_placeholder_replacement = True

        # step 1: preprocess code blocks
        md_src_processed = self._preprocess_code_blocks(md_src)

        # step 2: md -> html
        html_src = self._md_to_html(md_src_processed)
        self.html_results.append(html_src)

        # step 3: add proto-keys to html
        html_src2 = self._add_proto_keys_to_html(html_src, prefix=prefix)
        self.html_results.append(html_src2)

        # step 4: html -> md (with proto-keys)
        return self._html_to_md_with_proto_keys(html_src2)

    def markdownify_and_postprocess(self, html_src):
        """
        employ customized MarkdownConverter
        """

        mdc = mdf.MarkdownConverter(heading_style="ATX", bullets="-")

        # explicitly define conversion for strong and emphasized text
        mdc.convert_b = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "**"), mdc)
        mdc.convert_em = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "_"), mdc)

        # custom conversion for triple backtick code blocks
        def convert_code_triple_backticks(unused_self, el, text, convert_as_inline=None, parent_tags=None):
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

    def convert_plain_md_to_md_with_proto_keys(self) -> str:
        self.md_with_proto_keys = self.add_proto_keys_to_md(self.plain_md_src, prefix=self.proto_key_prefix)

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
