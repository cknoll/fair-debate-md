import re
from bs4 import BeautifulSoup, element


# characters which end a sentence / segment
SENTENCE_SPLITTERS = (".", "!", "?", ":")

# known abbreviations: after matching the abbreviation (case-sensitive,
# at a word boundary) we must NOT split, even if it ends with `.`.
# Each entry is matched against the text ending just before the splitter.
_ABBREVIATIONS = (
    "i.e.",
    "e.g.",
    "w.r.t.",
    "bspw.",
)

# version-number pattern: something like "v1." followed by a digit
# means the dot is part of a version number, not a sentence splitter.
_VERSION_RE = re.compile(r"v\d+\.$")


def _is_abbreviation_dot(text_so_far: str, text_rest: str) -> bool:
    """
    Decide whether a `.` at position `len(text_so_far)` (exclusive, i.e. the
    dot itself is the last char of `text_so_far`) belongs to an abbreviation
    and should therefore NOT be treated as a sentence splitter.

    :param text_so_far:  the text up to *and including* the candidate splitter
    :param text_rest:    the text after the candidate splitter (may start with
                         whitespace and then another abbreviation fragment)
    """
    # known fixed abbreviations ending at this dot
    for abbr in _ABBREVIATIONS:
        if text_so_far.endswith(abbr):
            return True

    # partial abbreviations like "i." (followed by "e." etc.)
    # we look at the short tail before the dot and check whether together
    # with the next non-space characters it forms a known abbreviation.
    stripped_rest = text_rest.lstrip()
    # consider up to 6 chars of tail before the dot (covers "w.r.t." etc.)
    for tail_len in range(2, 7):
        tail = text_so_far[-tail_len:]
        for abbr in _ABBREVIATIONS:
            if abbr.startswith(tail) and (tail + stripped_rest).startswith(abbr):
                return True

    # version number like "...v12." followed by a digit
    if _VERSION_RE.search(text_so_far) and stripped_rest[:1].isdigit():
        return True

    return False


def split_text_into_segments(text: str) -> list[str]:
    """
    Split `text` at sentence splitters (``.``, ``!``, ``?``, ``:``) into
    segments. Splitters stay attached to the preceding segment. Known
    abbreviations (``i.e.``, ``e.g.``, ``w.r.t.``, ``bspw.``) and version
    numbers (``v12.3``) do NOT cause a split.

    The concatenation of the returned segments equals the input text.

    This is a pure function intended to replace the convoluted index-based
    logic in `ProtoKeyAdder.insert_proto_keys` / `_abbreviation_handling`.
    """
    if not text:
        return []

    segments: list[str] = []
    start = 0
    for i, ch in enumerate(text):
        if ch not in SENTENCE_SPLITTERS:
            continue
        if ch == ".":
            text_so_far = text[: i + 1]
            text_rest = text[i + 1 :]
            if _is_abbreviation_dot(text_so_far, text_rest):
                continue
        # commit segment [start .. i] (inclusive of splitter)
        segments.append(text[start : i + 1])
        start = i + 1

    # trailing text (no final splitter)
    if start < len(text):
        segments.append(text[start:])

    return segments


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

        self.raw_parts = self._abbreviation_handling(self.original_parts)
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

        # We only want a key at the end if a sentence ends -> remove otherwise
        self.parts: list[str]
        if (
            len(self.parts)
            and self.parts[-1] == self.proto_key
            # the following means: the last real part is the end of a sentence
            and not self.parts[-2].strip()[-1] in (".", ":")
        ):
            self.parts.pop()

        res = element.NavigableString("".join(self.parts))
        res.added_keys = child.added_keys
        return res

    def _abbreviation_handling(self, original_parts):
        """
        Merge parts that belong together because they are part of an abbreviation
        (e.g. "i.e." was split into "i." and "e." by the sentence splitter).
        """
        # collect groups of indices which need to be joined
        self.parts_to_join = []
        idx = 0
        end = len(original_parts) - self.MAX_LOOK_AHEAD
        while idx < end:
            p0 = original_parts[idx]
            p1 = original_parts[idx + 1]
            p2 = original_parts[idx + 2]

            res_tup = self._classify_abbreviations(p0, p1, p2, idx)
            if res_tup is not None:
                self.parts_to_join.append(res_tup)
                idx = res_tup[-1]
            idx += 1

        # build a full partition of indices (join-groups + singletons)
        join_groups = self._expand_join_groups(
            self.parts_to_join, total_len=len(original_parts) - self.MAX_LOOK_AHEAD
        )

        res_parts = ["".join(original_parts[i] for i in tup) for tup in join_groups]

        # drop empty strings at the end
        while res_parts and res_parts[-1].strip() == "":
            res_parts.pop()

        return res_parts

    @staticmethod
    def _expand_join_groups(parts_to_join: list[tuple], total_len: int) -> list[tuple]:
        """
        Transform a list of join-specifiers into a full index partition.

        Input example:  [(1,), (4, 5)]  (meaning: after each index in the tuple
                        the following part should be joined to the previous)
        Step1 output:   [(1, 2), (4, 5, 6)]
        Step2 output:   [(0,), (1, 2), (3,), (4, 5, 6), (7,), (8,)]
        Overlapping groups like [(0, 1), (1, 2)] are merged into [(0, 1, 2)].
        """
        # step1: append the successor index to each group
        step1 = [tuple([*tup, tup[-1] + 1]) for tup in parts_to_join]

        # step2: fill in singletons and merge overlapping groups
        step2 = []
        idx = 0
        last_tup = None
        for tup in step1:
            for i in range(idx, tup[0]):
                step2.append((i,))
            if last_tup is not None and last_tup[-1] == tup[0]:
                step2[-1] = step2[-1][:-1] + tup
            else:
                step2.append(tup)
            last_tup = tup
            idx = tup[-1] + 1

        # ensure all remaining indices are included as singletons
        for i in range(idx, total_len):
            step2.append((i,))

        return step2

    def _classify_abbreviations(self, p1: str, p2: str, p3: str, idx: int) -> tuple[int] | None:
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
