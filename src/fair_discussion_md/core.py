import re
import markdown
import markdownify as mdf
from bs4 import BeautifulSoup, element

from ipydex import IPS


class HTMLProcessor:
    def __init__(self, html_src: str):
        self.html_src = html_src
        self.soup = BeautifulSoup(html_src, 'html.parser')
        self.blockified_tags = []

        self.sentence_splitters = [".", "!", "?", ":"]
        self.sentence_splitter_re = re.compile("([.?!:])")

    @staticmethod
    def will_be_processed_later(child):
        if isinstance(child, element.Tag) and child.name in ("p",):
            return True
        return False

    def add_proto_keys_to_html(self, prefix: str):

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
            self.add_proto_keys_to_tag(tag, prefix)
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


    def add_proto_keys_to_tag(self, tag: element.Tag, prefix: str):

        # get full source of inner_html (without surrounding <x attr="foo">...</x>)
        full_source = str(tag)
        idx1 = full_source.index(">")
        idx2 = full_source.rindex("<")
        inner_source = full_source[idx1 + 1:idx2]

        proto_key = f"::{prefix} "

        # convert all inner tags to monolithic blocks such that they are ignored
        # by the sentence splitter
        original_children = list(tag.children)
        tag.clear()
        part_counter = 0
        new_children = []
        for child in original_children:
            if new_children:
                optional_space = " "
            else:
                optional_space = ""
            if isinstance(child, element.Tag):
               self.blockify_tag(tag)
               new_children.append(child)
               continue
            assert isinstance(child, element.NavigableString)
            parts = self.sentence_splitter_re.split(child)
            part_without_delimiter = None
            for part in parts:
                if not part:
                    continue
                if part not in self.sentence_splitters:
                    part_without_delimiter = f"{optional_space}{proto_key} {part.strip()}"
                elif part_without_delimiter is not None:
                    new_children.append(f"{part_without_delimiter}{part}")
                else:
                    # part is a delimiter but there is no preceding "content-part"
                    new_children.append(part)

            # handle the case, when final substring is no delimiter
            if part_without_delimiter is not None:
                        new_children.append(f"{part_without_delimiter}{part}")
            # end of for child in original_children
        tag.extend(new_children)

        for tag in self.blockified_tags:
            self.unblockify_tag(tag)
        self.blockified_tags.clear()




def add_keys_to_md(md_src, prefix="a"):
    md = markdown.Markdown()
    html_src = md.convert(md_src)
    hp = HTMLProcessor(html_src)
    html_src2 = hp.add_proto_keys_to_html(prefix=prefix)
    md_src2 = mdf.markdownify(html_src2, heading_style="ATX", bullets="-")

    res = convert_tabs_to_spaces(md_src2)

    return res


def convert_tabs_to_spaces(input_string):
    lines = input_string.splitlines()

    def replace_tabs(line):
        leading_tabs = len(re.match(r'^\t*', line).group(0))
        return ' ' * (leading_tabs * 4) + line.lstrip('\t')
    converted_lines = [replace_tabs(line) for line in lines]
    return '\n'.join(converted_lines)


def main():
    pass