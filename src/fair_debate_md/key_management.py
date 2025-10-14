import re
from bs4 import BeautifulSoup, element

from ipydex import IPS


class ProtoKeyAdder:
    def __init__(self, html_src: str, prefix: str):
        self.html_src = html_src
        self.prefix = prefix
        self.proto_key = f" ::{self.prefix} "
        self.soup = BeautifulSoup(html_src, "html.parser")

        self.sentence_splitters = [".", "!", "?", ":"]
        self.sentence_splitter_re = re.compile("([.?!:])")
        self.parts: list = []

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

        # Problem: the current approach splits the incoming text not only at sentence delimiters but also
        # at abbreviations like "e.g.", "i.e.", "w.r.t." etc.
        #
        # TODO-AIDER: this should be prevented

        old_txt = str(child)
        start_idcs = [0]
        for match in matches:
            i0, i1 = match.span()
            start_idcs.append(i0 + 1)
        start_idcs.append(len(old_txt))

        # add some empty strings to allow look back for abbreviation checking
        self.MAX_LOOK_AHEAD = 2
        self.original_parts = [old_txt[i0:i1] for i0, i1 in zip(start_idcs[:-1], start_idcs[1:])]
        self.original_parts.extend([""]*self.MAX_LOOK_AHEAD)

        self.raw_parts = self.abbreviation_handling(self.original_parts)
        self.parts = []
        len_raw_parts = len(self.raw_parts)

        for counter, content in enumerate(self.raw_parts):

            self.parts.append(content)
            # TODO: handle space after delimiter (or as part of delimiter)
            if counter == len_raw_parts - 1:
                if len(content.rstrip()) < 4:
                    # do not add extra key for short strings after last sentence
                    continue
            self.parts.append(self.proto_key)
            child.added_keys += 1

        res = element.NavigableString("".join(self.parts))
        res.added_keys = child.added_keys
        return res

    def abbreviation_handling(self, original_parts):
        self.parts_to_join = []
        idx = 0
        end = len(original_parts) - self.MAX_LOOK_AHEAD
        while idx < end:
            p0 = original_parts[idx]
            p1 = original_parts[idx + 1]
            p2 = original_parts[idx + 2]

            res_tup = self.classify_abbreviations(p0, p1, p2, idx)
            if res_tup is not None:
                self.parts_to_join.append(res_tup)
                idx = res_tup[-1]
            idx += 1

        # transform parts_to_join:
        # currently looks like [(1, ), (4, 5)]
        # meaning: after each in index in the tuple the following part should be joined to the previous part
        # step1: convert to [(1, 2), (4, 5, 6)]

        parts_to_join_s1 = []
        for tup in self.parts_to_join:
                parts_to_join_s1.append(tuple([*tup, tup[-1] + 1]))

        # step2: convert to [ (0,), (1, 2), (3,), (4, 5, 6), (7,), (8,)]
        # also: convert [ (0, 1), (1, 2)] to [(0, 1, 2)]
        parts_to_join_s2 = []
        idx = 0
        last_tup = None
        for tup in parts_to_join_s1:
            for i in range(idx, tup[0]):
                parts_to_join_s2.append((i,))
            if last_tup is not None and last_tup[-1] == tup[0]:
                parts_to_join_s2[-1] = parts_to_join_s2[-1][:-1] + tup
            else:
                parts_to_join_s2.append(tup)
            last_tup = tup
            idx = tup[-1] + 1

        # also ensure that all indices of self.original_parts are included
        for i in range(idx, len(original_parts) - self.MAX_LOOK_AHEAD):
            parts_to_join_s2.append((i,))

        res_parts = []
        for tup in parts_to_join_s2:
            res_part_list = [self.original_parts[idx] for idx in tup]
            res_parts.append("".join(res_part_list))

        # drop empty strings at the end
        while res_parts and res_parts[-1].strip() == "":
            res_parts.pop()

        return res_parts





    def classify_abbreviations(self, p1: str, p2: str, p3: str, idx: int) -> tuple[int] | None:
        if p1.endswith("bspw."):
            return (idx, )
        if p1.endswith("i.") and p2 == "e.":
            return (idx, idx + 1)
        if p1.endswith("e.") and p2 == "g.":
            return (idx, idx + 1)
        if p1.endswith("w.") and p2 == "r." and p3 == "t.":
            return (idx, idx + 1, idx + 2)

        # version numbers
        # TODO: improve logic and add tests
        # maybe even require a whitespace after the dot to qualify as statement splitter
        self.version_number_pattern1 = re.compile(".*v[0-9]+")
        self.version_number_pattern2 = re.compile("[0-9]+")
        if self.version_number_pattern1.match(p1) and self.version_number_pattern2.match(p2):
            return (idx, idx + 1)
        return None

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
