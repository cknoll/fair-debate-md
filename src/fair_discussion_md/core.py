import re
import markdown
import markdownify as mdf
from bs4 import BeautifulSoup, element

from ipydex import IPS



def add_keys_to_html(html_src: str, prefix: str):
    soup = BeautifulSoup(html_src, 'html.parser')
    counter = 1

    def will_be_processed_later(child):
        if isinstance(child, element.Tag) and child.name in ("p"):
            return True
        return False


    # Prepend 'XYZ' to headings, paragraphs, list items, and code blocks
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'li', 'pre']):
        children_list = list(tag.children)
        if not children_list:
            continue
        elif will_be_processed_later(children_list[0]):
            continue
        elif children_list == ["\n"]:
            continue
        elif children_list[0] == "\n" and will_be_processed_later(children_list[1]):
            continue
        tag.insert(0, f"::{prefix}{counter};; ")
        counter += 1
    return str(soup)


def add_keys_to_md(md_src, prefix="a"):
    md = markdown.Markdown()
    html_src = md.convert(md_src)
    html_src2 = add_keys_to_html(html_src, prefix=prefix)
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