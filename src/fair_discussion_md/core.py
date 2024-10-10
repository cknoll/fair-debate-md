import markdown
from markdown.treeprocessors import Treeprocessor
from markdown.extensions import Extension

from ipydex import IPS


# generated from perplexity.ai
class ElementExtractor(Treeprocessor):
    def run(self, root):
        elements = []
        for element in root.iter():
            if element.tag == 'h1':
                elements.append({'type': 'heading', 'level': 1, 'content': element.text})
            elif element.tag == 'h2':
                elements.append({'type': 'heading', 'level': 2, 'content': element.text})
            elif element.tag == 'p':
                elements.append({'type': 'paragraph', 'content': element.text})
            elif element.tag == 'li':
                elements.append({'type': 'list_item', 'content': element.text})
            elif element.tag == 'code':
                elements.append({'type': 'code_block', 'content': element.text})
            else:
                print("unknown element:", element)
        return elements


class ElementExtension(Extension):
    def extendMarkdown(self, md):
        md.treeprocessors.register(ElementExtractor(md), 'element_extractor', 15)


class MarkdownCreator:
    """Convert Markdown AST back to a string."""
    pass


def markdown_to_string(root):
    result = []
    for elem in root.iter():
        if elem.tag == 'h1':
            result.append('# ' + (elem.text or '').strip())
        elif elem.tag == 'h2':
            result.append('## ' + (elem.text or '').strip())
        elif elem.tag == 'h3':
            result.append('### ' + (elem.text or '').strip())
        elif elem.tag == 'p':
            result.append((elem.text or '').strip())
        elif elem.tag == 'li':
            result.append('- ' + (elem.text or '').strip())
        elif elem.tag == 'pre':
            result.append('```\n' + (elem.text or '').strip() + '\n```')

    return '\n\n'.join(result)


def parse_markdown(markdown_text):
    md = markdown.Markdown(extensions=[ElementExtension()])
    # html = md.convert(markdown_text)
    md.parser.parseDocument(markdown_text.splitlines())
    return md.treeprocessors['element_extractor'].run(md.parser.root)


def main():
    pass