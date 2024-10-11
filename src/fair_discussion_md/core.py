import re
import types
import markdown
import markdownify as mdf
from bs4 import BeautifulSoup, element

from ipydex import IPS


class ProtoKeyAdder:
    def __init__(self, html_src: str, prefix: str):
        self.html_src = html_src
        self.prefix = prefix
        self.soup = BeautifulSoup(html_src, 'html.parser')
        self.blockified_tags = []

        self.sentence_splitters = [".", "!", "?", ":"]
        self.sentence_splitter_re = re.compile("([.?!:])")

    @staticmethod
    def will_be_processed_later(child):
        if isinstance(child, element.Tag) and child.name in ("p",):
            return True
        return False

    def add_proto_keys_to_html(self):

        for tag in self.soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'li', 'pre']):
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

    def split_into_sentences(self, txt: str):
        sentences = re.split(r'(?<=[.!?]) +', txt)
        return sentences

    def blockify_tag(self, tag: element.Tag):
        tag.original_children = list(tag.children)
        tag.original_attrs = tag.attrs.copy()

        tag.clear()
        tag.attrs.clear()
        self.blockified_tags.append(tag)

    def unblockify_tag(self, tag: element.Tag):
        tag.extend(tag.original_children)
        tag.attrs.update(tag.original_attrs)

    def add_proto_keys_to_tag(self, tag: element.Tag):
        # convert all inner tags to monolithic blocks such that they are ignored
        # by the sentence splitter
        original_children = list(tag.children)
        tag.clear()
        self.new_children = []
        for child in original_children:
            self.process_child_of_top_level_tag(child)


        tag.extend(self.new_children)

        for tag in self.blockified_tags:
            self.unblockify_tag(tag)

        # prepare data structures for the next run
        self.blockified_tags.clear()
        self.new_children.clear()

    def process_child_of_top_level_tag(self, child: element.PageElement):
        """
        This method writes to self.new_children
        """
        proto_key = f"::{self.prefix} "

        if self.new_children:
            # this is not the first subtag
            optional_space = " "
        else:
            optional_space = ""
        if isinstance(child, element.Tag):
            if not self.new_children:
                # if the first child is a subtag -> add a key
                self.new_children.append(f"{proto_key} ")
            else:
                self.new_children.append(" ")
            self.blockify_tag(child)
            self.new_children.append(child)
            return
        assert isinstance(child, element.NavigableString)

        parts = self.sentence_splitter_re.split(child)
        content_part = None
        for part in parts:
            if not part:
                continue
            if part not in self.sentence_splitters:
                content_part = f"{optional_space}{proto_key} {part.strip()}"
                continue
            elif content_part is not None:
                # part is a delimiter and we also have content-part
                self.new_children.append(f"{content_part}{part}")
                content_part = None
            else:
                # part is a delimiter but there is no preceding content-part
                # add it anyway
                self.new_children.append(part)

        # handle the case, when final substring is no delimiter
        if content_part is not None:
            self.new_children.append(f"{content_part}")
        return self.new_children


def markdownify(html_src):
    """
    employ customized MarkdownConverter
    """
    mdc = mdf.MarkdownConverter(heading_style="ATX", bullets="-")

    # explicitly define conversion for strong and emphasized text
    mdc.convert_b = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "**"), mdc)
    mdc.convert_em = types.MethodType(mdf.abstract_inline_conversion(lambda foo: "_"), mdc)
    return mdc.convert(html_src)


def add_proto_keys_to_md(md_src, prefix="k"):
    md = markdown.Markdown()
    html_src = md.convert(md_src)
    hp = ProtoKeyAdder(html_src, prefix=prefix)
    html_src2 = hp.add_proto_keys_to_html()
    md_src2 = markdownify(html_src2)

    res = convert_tabs_to_spaces(md_src2)

    return res


def convert_tabs_to_spaces(input_string):
    lines = input_string.splitlines()

    def replace_tabs(line):
        leading_tabs = len(re.match(r'^\t*', line).group(0))
        return ' ' * (leading_tabs * 4) + line.lstrip('\t')
    converted_lines = [replace_tabs(line) for line in lines]
    return '\n'.join(converted_lines)


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
        self.soup = BeautifulSoup(html_src, 'html.parser')
        self.pattern = r'(XXX\d+)'.replace("XXX", self.key_prefix)

        # compiled regex
        self.cre = re.compile(self.pattern)

    def add_spans_for_keys(self) -> str:
        root = self.soup
        self.process_children(root=root)
        return str(root.prettify())

    def process_children(self, root: element.Tag):
        original_children = list(root.children)
        root.clear()
        for child in original_children:
            new_child_list = self.process_child(child)
            root.extend(new_child_list)

        return root

    def process_child(self, child: element.PageElement):
        if isinstance(child, element.Tag):
            return [self.process_children(root=child)]

        assert isinstance(child, element.NavigableString)
        matches = list(self.cre.finditer(child.text))
        if not matches:
            return [child]
        res = []
        start_idcs = []
        end_idcs = []
        keys = []
        for match in matches:
            start_idcs.append(match.start())
            end_idcs.append(match.end())
            delimiter_key = match.group(1)  # something like "::a1"
            key = delimiter_key.replace("::", "")  # a1
            keys.append(key)

        # add final index at the end of the string
        start_idcs.append(len(child.text))

        # iterate over contents
        for i0, i1, key in zip(end_idcs, start_idcs[1:], keys):
            new_tag = element.Tag(name="span", attrs={"class": "segment", "id": key})
            content = child.text[i0:i1]
            new_tag.append(content)
            res.append(new_tag)

        return res


def get_html_with_segments(md_src, proto_key: str, prefix="a"):
    """
    Replace proto_keys by real numbered keys
    Convert markdown to html
    insert spans related to keys
    """

    md_src3 = KeyAdder(md_src).replace_proto_key_by_numbered_key(proto_key, prefix)
    md = markdown.Markdown()
    html_src = md.convert(md_src3)
    sa = SpanAdder(html_src, key_prefix=f"::{prefix}")
    res = sa.add_spans_for_keys()
    return html_src



def main():
    pass
