import re
from difflib import SequenceMatcher

STOP = set("""a an the is are was were be been of to in on for and or with by as at from that this
these those it its into can may which what when how why who will would should could do does
such than then there their they them we you your our also using use used""".split())


def content_tokens(t):
    return [w for w in re.findall(r"[a-zA-Z_]+", t.lower()) if w not in STOP and len(w) > 2]


def token_recall(part, whole):
    p = content_tokens(part)
    if not p:
        return 0.0
    w = set(content_tokens(whole))
    return sum(1 for x in p if x in w) / len(p)


def span_ratio(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()
