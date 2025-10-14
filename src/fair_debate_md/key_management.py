import re
from bs4 import BeautifulSoup, element


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
