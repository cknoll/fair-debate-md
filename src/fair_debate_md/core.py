import re
import os
import glob
import types
import markdown
import markdownify as mdf
from bs4 import BeautifulSoup, element

from ipydex import IPS

pjoin  = os.path.join


class ProtoKeyAdder:
    def __init__(self, html_src: str, prefix: str):
        self.html_src = html_src
        self.prefix = prefix
        self.proto_key = f" ::{self.prefix} "
        self.soup = BeautifulSoup(html_src, "html.parser")

        self.sentence_splitters = [".", "!", "?", ":"]
        self.sentence_splitter_re = re.compile("([.?!:])")

    @staticmethod
    def will_be_processed_later(child):
        if isinstance(child, element.Tag) and child.name in ("p",):
            return True
        return False

    def add_proto_keys_to_html(self):
        for tag in self.soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "li", "pre"]):
            children_list = list(tag.children)
            if not children_list:
                continue
            elif self.will_be_processed_later(children_list[0]):
                continue
            elif children_list == ["\n"]:
                continue
            elif children_list[0] == "\n" and self.will_be_processed_later(children_list[1]):
                continue
            self.add_proto_keys_to_tag(tag)
        return str(self.soup)

    def insert_proto_keys(self, child: element.NavigableString):
        child.added_keys = 0
        matches = list(self.sentence_splitter_re.finditer(child))
        if not matches:
            # nothing changed
            return child

        old_txt = str(child)
        start_idcs = [0]
        for match in matches:
            i0, i1 = match.span()
            start_idcs.append(i0 + 1)
        start_idcs.append(len(old_txt))

        parts = []
        for counter, (i0, i1) in enumerate(zip(start_idcs[:-1], start_idcs[1:])):
            # add the content until the delimiter
            content = old_txt[i0:i1]
            parts.append(content)
            # TODO: handle space after delimiter (or as part of delimiter)
            if counter == len(start_idcs) - 2:
                if len(content.rstrip()) < 4:
                    # do not add extra key for short strings after last sentence
                    continue
            parts.append(self.proto_key)
            child.added_keys += 1

        res = element.NavigableString("".join(parts))
        res.added_keys = child.added_keys
        return res

    def add_proto_keys_to_tag(self, tag: element.Tag, level=0):
        original_children = list(tag.children)

        tag.clear()
        new_children = [self.proto_key.lstrip()]
        for child in original_children:
            if isinstance(child, element.Tag):
                # TODO: handle nested tags (e.g.  sentence delimiter within em-tags)
                new_children.append(child)
            else:
                assert isinstance(child, element.NavigableString)
                new_str = self.insert_proto_keys(child)
                new_children.append(new_str)

        if level == 0:
            if isinstance(new_children[-1], element.NavigableString):
                if new_children[-1].rstrip().endswith(self.proto_key.strip()):
                    idx = new_children[-1].rindex(self.proto_key)
                    tmp1 = new_children[-1][:idx]
                    tmp2 = new_children[-1][idx + len(self.proto_key) :]
                    new_children[-1] = element.NavigableString(f"{tmp1}{tmp2}")

        tag.extend(new_children)
        return


def markdownify_and_postprocess(html_src):
    """
    employ customized MarkdownConverter
    """
    mdc = mdf.MarkdownConverter(heading_style="ATX", bullets="-")

    # explicitly define conversion for strong and emphasized text
    mdc.convert_b = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "**"), mdc)
    mdc.convert_em = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "_"), mdc)

    res0 = mdc.convert(html_src)
    res1 = convert_tabs_to_spaces(res0)

    return res1


def add_proto_keys_to_md(md_src, prefix="k"):
    md = markdown.Markdown()
    html_src = md.convert(md_src)
    pka = ProtoKeyAdder(html_src, prefix=prefix)
    html_src2 = pka.add_proto_keys_to_html()
    res = markdownify_and_postprocess(html_src2)
    return res


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
    def __init__(self, html_src: str, key_prefix: str):
        self.html_src = html_src
        self.key_prefix = key_prefix
        self.soup = BeautifulSoup(html_src, "html.parser")
        self.pattern = r" ?(XXX\d+)".replace("XXX", self.key_prefix)
        self.span_tag_is_open = False
        self.encoded_left_delimiter = "_[_"
        self.encoded_right_delimiter = "_]_"

        self.active_tag_stack = []

        # compiled regex
        self.cre = re.compile(self.pattern)

    def add_spans_for_keys(self, prettify: bool = False) -> str:
        root = self.soup
        self.process_children(root=root, level=0)
        if prettify:
            res = str(root.prettify())
        else:
            res = str(root)

        res2 = self.insert_encoded_delimiters(res)
        return res2

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

    def process_child(self, child: element.PageElement, level: int):
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
        return res

    def encode_tags(self, txt):
        return txt.replace("<", self.encoded_left_delimiter).replace(">", self.encoded_right_delimiter)

    def insert_encoded_delimiters(self, txt):
        return txt.replace(self.encoded_left_delimiter, "<").replace(self.encoded_right_delimiter, ">")


class MDProcessor:

    def __init__(self, plain_md: str = None, proto_key_prefix="k", key_prefix="a", md_with_real_keys: str = None):
        self.plain_md_src = plain_md

        self.proto_key_prefix = proto_key_prefix
        self.key_prefix = key_prefix

        self.md_with_proto_keys: str = None
        self.md_with_real_keys = md_with_real_keys
        self.segmented_html: str = None

    def convert(self):
        self.convert_plain_md_to_md_with_proto_keys()
        self.convert_md_with_proto_keys_to_md_with_real_keys()
        self.get_html_with_segments()

    def convert_plain_md_to_md_with_proto_keys(self) -> str:
        self.md_with_proto_keys = add_proto_keys_to_md(self.plain_md_src, prefix=self.proto_key_prefix)

    def convert_md_with_proto_keys_to_md_with_real_keys(self) -> str:
        proto_key=f"::{self.proto_key_prefix}"
        self.md_with_real_keys = KeyAdder(self.md_with_proto_keys).replace_proto_key_by_numbered_key(proto_key, self.key_prefix)
        return self.md_with_real_keys

    def get_html_with_segments(self):
        """
        Convert markdown to html
        insert spans related to keys
        """

        md = markdown.Markdown()
        html_src = md.convert(self.md_with_real_keys)
        sa = SpanAdder(html_src, key_prefix=f"::{self.key_prefix}")
        res = sa.add_spans_for_keys()

        self.segmented_html = res
        return self.segmented_html


def convert_plain_md_to_segmented_html(md_src: str, key_prefix="k") -> str:
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


class DebateDirLoader:

    def __init__(self, dirpath):
        self.dirpath=dirpath
        self.dir_a = pjoin(self.dirpath, "a")
        self.dir_b = pjoin(self.dirpath, "b")
        self.root_file = pjoin(self.dir_a, "a.md")

        self.mdp_list: list[MDProcessor] = []

        self.tree: dict[str, MDProcessor] = {}

    def load_dir(self):

        a_files = glob.glob(pjoin(self.dir_a, "*.md"))
        b_files = glob.glob(pjoin(self.dir_b, "*.md"))

        all_files = [fpath for fpath in a_files + b_files if is_valid_fpath(fpath)]
        all_files.sort()

        self.mdp_list = []

        for fpath in all_files:
            base_name = get_base_name(fpath)

            with open(fpath, "r") as fp:
                md_with_real_keys = fp.read()
            mdp = MDProcessor(key_prefix=base_name, md_with_real_keys=md_with_real_keys)
            self.tree[base_name] = mdp

            # TODO: necessary?
            self.mdp_list.append(mdp)


def load_dir(dirpath):
    ddl = DebateDirLoader(dirpath=dirpath)
    ddl.load_dir()
    return ddl






def main():
    pass
