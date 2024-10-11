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
        self.proto_key = f" ::{self.prefix} "
        self.soup = BeautifulSoup(html_src, 'html.parser')

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
                if len(content.rstrip())< 4:
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
                    tmp2 = new_children[-1][idx+len(self.proto_key):]
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

    def add_spans_for_keys(self, prettify: bool = False) -> str:
        root = self.soup
        self.process_children(root=root)
        if prettify:
            res = str(root.prettify())
        else:
            res = str(root)
        return res

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
    return res



def main():
    pass
