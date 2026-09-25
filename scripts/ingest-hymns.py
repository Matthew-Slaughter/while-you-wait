#!/usr/bin/env python3
"""ingest-hymns.py: emit single-stanza hymn entries from public-domain texts.

Every stanza is copied verbatim from a file under sources/ (whitespace
normalized; editorial markup such as Gutenberg `_italics_` and abc `\\-`
soft hyphens removed; nothing reworded). Only hymnwriters and translators
who died before 1930 are admitted; see AUTHORS. The stanzas taken are
chosen by hand in PICKS (well-known hymns, strongest stanzas) and located
in the source by the first words of the stanza, so a changed source file
fails loudly instead of silently shifting stanzas.

Sources (see docs/SOURCES.md):
  gutenberg/pg13341.txt          Watts, Hymns and Spiritual Songs (1707-9)
  ccel/newton-olneyhymns.txt     Newton & Cowper, Olney Hymns (1779)
  ccel/wesley/jwgNNNN.html       Wesley, A Collection of Hymns (1780; 1889 ed.)
  gutenberg/pg4272.txt           Keble, The Christian Year (1827)
  gutenberg/pg30362.txt          Gerhardt, Spiritual Songs tr. John Kelly (1867)
  gutenberg/pg26874.txt          Toplady, Rock of Ages (1776; 1909 printing)
  gutenberg/pg31647.txt          Havergal, Kept for the Master's Use (1879)
  openhymnal/Complete/*/*.abc    Open Hymnal Project abc files (W: stanza blocks)

Usage:
  python3 scripts/ingest-hymns.py [--out corpus/incoming/hymns.json] [-v]
"""
import argparse
import glob
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(ROOT, "sources")
DEFAULT_OUT = os.path.join(ROOT, "corpus", "incoming", "hymns.json")
ADDED = "0.6.0"
MAX_CHARS = 420
MAX_PER_HYMN = 6
MAX_PER_AUTHOR = 25
PD_CUTOFF = 1930  # author (and translator) must have died before this year

# slug -> (display name, died)
AUTHORS = {
    "watts": ("Isaac Watts", 1748),
    "newton": ("John Newton", 1807),
    "cowper": ("William Cowper", 1800),
    "wesley": ("Charles Wesley", 1788),
    "keble": ("John Keble", 1866),
    "gerhardt": ("Paul Gerhardt", 1676),
    "toplady": ("Augustus Toplady", 1778),
    "havergal": ("Frances Ridley Havergal", 1879),
    "lyte": ("Henry Francis Lyte", 1847),
    "rippon": ("John Rippon", 1836),
    "bernard": ("Bernard of Clairvaux", 1153),
    "ken": ("Thomas Ken", 1711),
    "medley": ("Samuel Medley", 1799),
    "montgomery": ("James Montgomery", 1854),
    "stone": ("Samuel John Stone", 1900),
    "how": ("William Walsham How", 1897),
    "fawcett": ("John Fawcett", 1817),
    "luther": ("Martin Luther", 1546),
    "pierpoint": ("Folliott Sandford Pierpoint", 1917),
    "wordsworth": ("Christopher Wordsworth", 1885),
    "barton": ("Bernard Barton", 1849),
    "synesius": ("Synesius of Cyrene", 414),
    "morison": ("John Morison", 1798),
    "plumptre": ("Edward Hayes Plumptre", 1891),
    "anon15c": ("Anonymous (15th century)", 1500),
    "coffin": ("Charles Coffin", 1749),
    "everest": ("Charles William Everest", 1877),
    "march": ("Daniel March", 1909),
}
TRANSLATORS = {
    "kelly": ("John Kelly", 1890),
    "winkworth": ("Catherine Winkworth", 1878),
    "alexander": ("James Waddell Alexander", 1859),
    "massie": ("Richard Massie", 1887),
    "cox": ("Frances Elizabeth Cox", 1897),
    "chatfield": ("Allen William Chatfield", 1896),
    "webb": ("Benjamin Webb", 1885),
    "chandler": ("John Chandler", 1876),
}

# ---------------------------------------------------------------------------
# PICKS: (source, hymn locator, author slug, year, stanza picks, translator)
# A stanza pick is either the stanza number (int) or the first words of the
# stanza (str, matched case-insensitively against the stanza's first line).
# Order matters: per-author and per-hymn caps keep the earliest picks.
PICKS = [
    # --- Isaac Watts, Hymns and Spiritual Songs (Gutenberg 13341) ----------
    ("watts", "When I survey the wondrous cross", "watts", 1707, ["When I survey", "See from his head", "Were the whole realm"]),
    ("watts", "Alas! and did my Saviour bleed", "watts", 1707, ["Alas! and did", "But drops of grief"]),
    ("watts", "Come, we that love the Lord", "watts", 1707, [1]),
    ("watts", "How sweet and awful is the place", "watts", 1707, [1]),
    ("watts", "Join all the glorious names", "watts", 1707, [1]),
    ("watts", "Not all the blood of beasts", "watts", 1709, ["Not all the blood", "My faith would lay"]),
    ("watts", "There is a land of pure delight", "watts", 1707, [1]),
    ("watts", "Give me the wings of faith", "watts", 1709, [1]),
    ("watts", "Come, Holy Spirit, heavenly Dove", "watts", 1707, [1]),
    ("watts", "Hark! from the tombs a doleful sound", "watts", 1707, [1]),
    ("watts", "Nature with open volume stands", "watts", 1707, [1]),
    ("watts", "Begin, my tongue, some heavenly theme", "watts", 1707, [1]),
    ("watts", "How condescending and how kind", "watts", 1709, [1]),
    ("watts", "With joy we meditate the grace", "watts", 1709, [1]),
    ("watts", "Why should we start, and fear to die", "watts", 1707, [1]),
    ("watts", "The Lord Jehovah reigns", "watts", 1707, [1]),
    ("watts", "I give immortal praise", "watts", 1707, [1]),
    ("watts", "Salvation! O the joyful sound", "watts", 1707, [1]),
    ("watts", "When I can read my title clear", "watts", 1707, [1]),
    ("watts", "Great God, how infinite art thou", "watts", 1707, [1]),
    ("watts", "No more, my God, I boast no more", "watts", 1709, [1]),
    ("watts", "Dearest of all the names above", "watts", 1709, [1]),
    ("watts", "How vast the treasure we possess", "watts", 1709, [1]),
    ("watts", "Let others boast how strong they be", "watts", 1709, [1]),
    # --- John Newton, Olney Hymns (CCEL) ------------------------------------
    ("olney", "Amazing grace!", "newton", 1779, ["Amazing grace", "Through many dangers", "The earth shall soon"]),
    ("olney", "How sweet the name of Jesus sounds", "newton", 1779, ["How sweet the name", "Dear name! the rock", "Jesus! my Shepherd"]),
    ("olney", "Glorious things of thee are spoken", "newton", 1779, ["Glorious things", "See! the streams"]),
    ("olney", "Begone unbelief", "newton", 1779, ["Begone unbelief", "Though dark be my way"]),
    ("olney", "One there is, above all others", "newton", 1779, [1]),
    ("olney", "Approach, my soul, the mercy-seat", "newton", 1779, ["Approach, my soul", "Thy promise is my only plea"]),
    ("olney", "Let us love, and sing, and wonder", "newton", 1779, [1]),
    ("olney", "Safely through another week", "newton", 1779, [1]),
    ("olney", "In evil long I took delight", "newton", 1779, ["In evil long", "I saw One hanging"]),
    ("olney", "I asked the Lord that I might grow", "newton", 1779, [1]),
    ("olney", "Though troubles assail", "newton", 1779, [1]),
    ("olney", "Why should I fear the darkest hour", "newton", 1779, [1]),
    ("olney", "Precious Bible! what a treasure", "newton", 1779, [1]),
    ("olney", "Quiet, Lord, my froward heart", "newton", 1779, [1]),
    ("olney", "Come, my soul, thy suit prepare", "newton", 1779, ["Come, my soul", "Thou art coming to a King"]),
    ("olney", "Physician of my sin-sick soul", "newton", 1779, [1]),
    ("olney", "Behold the throne of grace", "newton", 1779, [1]),
    ("olney", "Now may the Lord reveal his face", "newton", 1779, [1]),
    ("olney", "While with ceaseless course the sun", "newton", 1779, [1]),
    ("olney", "How tedious and tasteless the hours", "newton", 1779, [1]),
    # --- William Cowper, Olney Hymns (CCEL) ---------------------------------
    ("olney", "God moves in a mysterious way", "cowper", 1774, ["God moves", "Deep in unfathomable mines", "Ye fearful saints", "Judge not the Lord", "His purposes will ripen", "Blind unbelief"]),
    ("olney", "There is a fountain", "cowper", 1772, ["There is a fountain", "The dying thief", "Dear dying Lamb", "E'er since, by faith"]),
    ("olney", "O! for a closer walk with God", "cowper", 1772, ["O! for a closer", "Return, O holy Dove", "So shall my walk"]),
    ("olney", "Sometimes a light surprises", "cowper", 1779, ["Sometimes a light", "The vine, nor fig-tree"]),
    ("olney", "Hark, my soul! it is the Lord", "cowper", 1768, ["Hark, my soul", "Can a woman's tender care"]),
    ("olney", "Jesus, where'er thy people meet", "cowper", 1769, ["Jesus, where'er", "For thou, within no walls"]),
    ("olney", "What various hindrances we meet", "cowper", 1779, [1]),
    ("olney", "Ere God had built the mountains", "cowper", 1779, [1]),
    ("olney", "The billows swell, the winds are high", "cowper", 1779, [1]),
    ("olney", "To keep the lamp alive", "cowper", 1779, [1]),
    ("olney", "Far from the world, O Lord, I flee", "cowper", 1779, [1]),
    ("olney", "O Lord, my best desire fulfil", "cowper", 1779, [1]),
    ("olney", "God of my life, to thee I call", "cowper", 1779, [1]),
    # --- Charles Wesley, A Collection of Hymns (CCEL html pages) ------------
    ("wesley", "jwg0001", "wesley", 1739, ["O FOR a thousand", "Jesus! the name that charms", "He breaks the power", "He speaks, and, listening"]),
    ("wesley", "jwg0143", "wesley", 1740, ["JESU, Lover", "Other refuge have I none", "Plenteous grace with thee"]),
    ("wesley", "jwg0201", "wesley", 1738, ["'Tis mystery all", "Long my imprisoned", "No condemnation"]),
    ("wesley", "jwg0385", "wesley", 1747, ["LOVE Divine, all loves", "Finish then thy new creation"]),
    ("wesley", "jwg0729", "wesley", 1744, ["REJOICE, the Lord", "His kingdom cannot fail"]),
    ("wesley", "jwg0266", "wesley", 1749, ["SOLDIERS of Christ", "Stand then in his great might"]),
    ("wesley", "jwg0683", "wesley", 1739, ["HARK the herald"]),
    ("wesley", "jwg0688", "wesley", 1744, ["COME, thou long-expected", "Born thy people to deliver"]),
    ("wesley", "jwg0140", "wesley", 1742, ["COME, O thou Traveller"]),
    ("wesley", "jwg0168", "wesley", 1740, ["DEPTH of mercy"]),
    ("wesley", "jwg0190", "wesley", 1740, ["JESU, thy blood", "Bold shall I stand"]),
    ("wesley", "jwg0194", "wesley", 1742, ["ARISE, my soul"]),
    ("wesley", "jwg0343", "wesley", 1742, ["O FOR a heart"]),
    ("wesley", "jwg0531", "wesley", 1740, ["CHRIST, whose glory"]),
    ("wesley", "jwg0324", "wesley", 1749, ["FORTH in thy name"]),
    ("wesley", "jwg0318", "wesley", 1762, ["A CHARGE to keep"]),
    ("wesley", "jwg0859", "wesley", 1744, ["YE servants of God"]),
    # --- John Keble, The Christian Year (Gutenberg 4272) --------------------
    ("keble", "Morning.", "keble", 1827, ["New every morning", "New mercies, each returning", "The trivial round", "Only, O Lord, in Thy dear love", "Old friends, old scenes"]),
    ("keble", "Evening.", "keble", 1827, ["Sun of my soul", "When the soft dews", "Abide with me from morn", "Watch by the sick", "Oh! by Thine own sad burthen"]),
    ("keble", "Septuagesima Sunday.", "keble", 1827, ["There is a book", "Two worlds are ours"]),
    ("keble", "Advent Sunday.", "keble", 1827, [1]),
    ("keble", "Christmas Day.", "keble", 1827, [1]),
    ("keble", "Easter Day.", "keble", 1827, [1]),
    ("keble", "Whitsunday.", "keble", 1827, [1]),
    ("keble", "Trinity Sunday.", "keble", 1827, [1]),
    # --- Paul Gerhardt tr. John Kelly (Gutenberg 30362) ---------------------
    ("gerhardt", "Commit whatever grieves thee", "gerhardt", 1653, [1, 2], "kelly"),
    ("gerhardt", "Oh! bleeding head, and wounded", "gerhardt", 1656, [1, 2], "kelly"),
    ("gerhardt", "A Lamb bears all its guilt away", "gerhardt", 1647, [1], "kelly"),
    ("gerhardt", "Awake, my heart! be singing", "gerhardt", 1647, [1, 2], "kelly"),
    ("gerhardt", "Is God for me?", "gerhardt", 1653, [1], "kelly"),
    ("gerhardt", "Why should sorrow ever grieve me", "gerhardt", 1653, [1], "kelly"),
    ("gerhardt", "Now with joy my heart is bounding", "gerhardt", 1653, [1], "kelly"),
    ("gerhardt", "Up! up! my heart with gladness", "gerhardt", 1648, [1], "kelly"),
    ("gerhardt", "O Jesus Christ! my fairest Light", "gerhardt", 1653, [1], "kelly"),
    ("gerhardt", "Now spread are evening's shadows", "gerhardt", 1647, [1], "kelly"),
    ("gerhardt", "Go forth, my heart, and seek delight", "gerhardt", 1653, [1], "kelly"),
    ("gerhardt", "Jesus! Thou, my dearest Brother", "gerhardt", 1653, [1], "kelly"),
    ("gerhardt", "O Lord! I sing with mouth and heart", "gerhardt", 1653, [1], "kelly"),
    ("gerhardt", "The golden morning", "gerhardt", 1666, [1], "kelly"),
    ("gerhardt", "Shall I not my God be praising", "gerhardt", 1653, [1], "kelly"),
    ("gerhardt", "Immanuel! to Thee we sing", "gerhardt", 1653, [1], "kelly"),
    ("gerhardt", "Now at the manger here I stand", "gerhardt", 1653, [1], "kelly"),
    # --- Toplady, Rock of Ages (Gutenberg 26874) ----------------------------
    ("toplady", "Rock of ages", "toplady", 1776, [1, 2, 3, 4]),
    # --- Havergal, Take My Life (Gutenberg 31647) ---------------------------
    ("havergal", "Take my life", "havergal", 1874, [1, 2, 3, 4, 5, 6]),
    # --- Open Hymnal Project abc files (W: blocks hold the later stanzas) ---
    ("openhymnal", "Abide_With_Me", "lyte", 1847, [7, 8, 6]),
    ("openhymnal", "How_Firm_A_Foundation", "rippon", 1787, [7, 6]),
    ("openhymnal", "O_Sacred_Head_Now_Wounded", "bernard", 1153, [6, 7, 11], "alexander"),
    ("openhymnal", "All_My_Heart_This_Night_Rejoices", "gerhardt", 1656, [6, 9, 7, 8], "winkworth"),
    ("openhymnal", "Awake_My_Soul_And_With_The_Sun", "ken", 1674, [9, 11, 6, 8]),
    ("openhymnal", "All_Praise_To_Thee_My_God_This_Night", "ken", 1674, [6]),
    ("openhymnal", "I_Know_That_My_Redeemer_Lives", "medley", 1775, [6, 7, 8]),
    ("openhymnal", "Angels_From_The_Realms_Of_Glory", "montgomery", 1816, [7]),
    ("openhymnal", "The_Churchs_One_Foundation", "stone", 1866, [6, 7]),
    ("openhymnal", "For_All_The_Saints", "how", 1864, [11]),
    ("openhymnal", "We_Give_Thee_But_Thine_Own", "how", 1864, [6]),
    ("openhymnal", "Blest_Be_The_Tie_That_Binds", "fawcett", 1782, [6]),
    ("openhymnal", "To_Shepherds_as_They_Watched_By_Night", "luther", 1543, [6], "massie"),
    ("openhymnal", "Look_Down_O_Lord_From_Heaven_Behold", "luther", 1524, [6], "cox"),
    ("openhymnal", "For_The_Beauty_Of_The_Earth", "pierpoint", 1864, [8]),
    ("openhymnal", "Sing_O_Sing_This_Blessed_Morn", "wordsworth", 1865, [6, 11, 7]),
    ("openhymnal", "The_Winds_And_Billows_Loudly_Roar", "wordsworth", 1865, [7]),
    ("openhymnal", "Lamp_of_Our_Feet", "barton", 1826, [9, 6]),
    ("openhymnal", "Lord_Jesus_Think_On_Me", "synesius", 430, [6, 7], "chatfield"),
    ("openhymnal", "The_People_That_in_Darkness_Sat", "morison", 1781, [7]),
    ("openhymnal", "Rejoice_O_Pilgrim_Throng", "plumptre", 1865, [7, 8, 6]),
    ("openhymnal", "O_Love_How_Deep", "anon15c", 1500, [7, 8], "webb"),
    ("openhymnal", "Take_Up_Thy_Cross_The_Savior_Said", "everest", 1833, [6]),
    ("openhymnal", "The_Advent_of_Our_God", "coffin", 1736, [6], "chandler"),
    ("openhymnal", "Hark_The_Voice_Of_Jesus_Calling", "march", 1868, [6]),
]

WORKS = {
    "watts": ("Hymns and Spiritual Songs (1707)", "gutenberg.org/ebooks/13341", "gutenberg/pg13341.txt"),
    "olney": ("Olney Hymns (1779)", "ccel.org/ccel/newton/olneyhymns", "ccel/newton-olneyhymns.txt"),
    "wesley": ("A Collection of Hymns for the Use of the People Called Methodists (1780; 1889 ed.)", "ccel.org/w/wesley/hymn", None),
    "keble": ("The Christian Year (1827)", "gutenberg.org/ebooks/4272", "gutenberg/pg4272.txt"),
    "gerhardt": ("Paul Gerhardt's Spiritual Songs, tr. John Kelly (1867)", "gutenberg.org/ebooks/30362", "gutenberg/pg30362.txt"),
    "toplady": ("Rock of Ages (1776; 1909 printing)", "gutenberg.org/ebooks/26874", "gutenberg/pg26874.txt"),
    "havergal": ("Kept for the Master's Use (1879)", "gutenberg.org/ebooks/31647", "gutenberg/pg31647.txt"),
    "openhymnal": ("Open Hymnal Project", "mzealey/openhymnal", None),
}

# ---------------------------------------------------------------------------
_WS = re.compile(r"[ \t]+")


def clean_line(s):
    s = s.replace("\\-", "")            # abc soft hyphen
    s = re.sub(r"_([^_]+)_", r"\1", s)  # Gutenberg italics
    return _WS.sub(" ", s).strip()


_MARGINAL_REF = re.compile(r"^\s*(?:[1-3]\s*)?[A-Z][a-z]{1,5}\.?\s*\d+[:.,\d\s-]*\s*$")


def stanza_text(lines):
    # Hymnals print a marginal scripture reference (e.g. "Ps 87:3", "Jn 8:7")
    # as its own line inside a stanza; it is apparatus, not the hymn.
    kept = [clean_line(l) for l in lines if clean_line(l)]
    return "\n".join(l for l in kept if not _MARGINAL_REF.match(l))


def read(rel):
    with open(os.path.join(SOURCES, rel), encoding="utf-8", errors="replace") as f:
        return f.read()


class Hymn:
    def __init__(self, source, locator, path_frag, stanzas, numbers=None, author_hint=None):
        self.source = source
        self.locator = locator          # what PICKS matches against
        self.path_frag = path_frag      # witness.path
        self.stanzas = stanzas          # list of verbatim stanza texts
        self.numbers = numbers or list(range(1, len(stanzas) + 1))
        self.author_hint = author_hint

    def first_line(self):
        return self.stanzas[0].split("\n")[0] if self.stanzas else ""


# ---------- parsers ---------------------------------------------------------

def parse_watts():
    raw = read(WORKS["watts"][2])
    lines = raw.split("\n")
    hymns, state = [], {"cur": None, "stanzas": [], "buf": None}

    def close_stanza():
        b = state["buf"]
        if b is not None:
            num, br, ls = b
            # Watts' brackets mark stanzas that may be omitted in singing; the
            # words are his, only the bracket characters are apparatus
            state["stanzas"].append((num, br, stanza_text(ls).lstrip("[").rstrip("]")))
            state["buf"] = None

    def close_hymn():
        close_stanza()
        cur, stanzas = state["cur"], state["stanzas"]
        if cur and stanzas:
            h = Hymn("watts", stanzas[0][2].split("\n")[0], "gutenberg/pg13341.txt#Hymn %s" % cur, [], [])
            for num, br, txt in stanzas:
                h.stanzas.append(txt)
                h.numbers.append(num)
            if h.stanzas:
                hymns.append(h)
        state["cur"], state["stanzas"] = None, []

    for line in lines:
        m = re.match(r"^Hymn (\d+):(\d+)\.", line)
        if m:
            close_hymn()
            state["cur"] = "%s:%s" % (m.group(1), m.group(2))
            continue
        s = re.match(r"^(\d+) (\[?)([A-Za-z'\"].*)$", line)
        if s and state["cur"]:
            close_stanza()
            state["buf"] = [int(s.group(1)), bool(s.group(2)), [s.group(3)]]
            continue
        if state["buf"] is not None:
            if not line.strip():
                close_stanza()
            else:
                state["buf"][2].append(line)
    close_hymn()
    return hymns


def parse_olney():
    raw = read(WORKS["olney"][2])
    lines = raw.split("\n")
    book = "?"
    hymns = []
    i = 0
    idx = [k for k, l in enumerate(lines) if re.match(r"^Hymn \d+\s*$", l)]
    for k, start in enumerate(idx):
        # book marker is the last "BOOK N." line above this header
        for j in range(start, -1, -1):
            b = re.match(r"^BOOK (I{1,3})\.\s*$", lines[j])
            if b:
                book = b.group(1)
                break
        num = re.match(r"^Hymn (\d+)", lines[start]).group(1)
        end = idx[k + 1] if k + 1 < len(idx) else len(lines)
        body = lines[start + 1:end]
        # preamble ends at the first run of >= 2 blank lines
        j, blank = 0, 0
        pre = []
        while j < len(body):
            if body[j].strip():
                pre.append(body[j].strip())
                blank = 0
            else:
                blank += 1
                if blank >= 2 and pre:
                    break
            j += 1
        author = pre[0] if pre else ""
        stanzas, cur, blank = [], [], 0
        for line in body[j:]:
            if re.match(r"^\s*_{10,}\s*$", line):
                break
            if line.strip():
                cur.append(line)
                blank = 0
            else:
                blank += 1
                if blank >= 2 and cur:
                    stanzas.append(stanza_text(cur))
                    cur = []
        if cur:
            stanzas.append(stanza_text(cur))
        if stanzas:
            hymns.append(Hymn("olney", stanzas[0].split("\n")[0],
                              "ccel/newton-olneyhymns.txt#Book %s, Hymn %s" % (book, num), stanzas, author_hint=author))
    return hymns


def parse_wesley():
    hymns = []
    for path in sorted(glob.glob(os.path.join(SOURCES, "ccel", "wesley", "jwg*.html"))):
        raw = read(os.path.relpath(path, SOURCES))
        body = re.search(r"<BODY>(.*?)</BODY>", raw, re.S | re.I)
        if not body:
            continue
        stanzas, numbers = [], []
        for block in re.split(r"<P>", body.group(1), flags=re.I):
            txt = html.unescape(re.sub(r"<BR>", "\n", block, flags=re.I))
            txt = re.sub(r"<[^>]+>", "", txt)
            txt = re.sub(r"^==.*$", "", txt, flags=re.M)  # "==L.M. SECOND PART." dividers
            ls = [l for l in txt.split("\n") if l.strip()]
            if not ls:
                continue
            m = re.match(r"^\s*(\d+) (.*)$", ls[0])
            if not m:
                continue
            ls[0] = m.group(2)
            stanzas.append(stanza_text(ls))
            numbers.append(int(m.group(1)))
        stem = os.path.basename(path)[:-5]
        hymns.append(Hymn("wesley", stem, "ccel/wesley/%s.html" % stem, stanzas, numbers))
    return hymns


def parse_keble():
    raw = read(WORKS["keble"][2])
    lines = raw.split("\n")
    hymns, title, cur, stanzas = [], None, [], []

    def flush():
        if title and stanzas:
            hymns.append(Hymn("keble", title, "gutenberg/pg4272.txt#%s" % title, list(stanzas)))

    for line in lines:
        if re.match(r"^[A-Z][A-Za-z ,'’.-]{2,60}\.$", line) and not line.startswith(" "):
            if cur:
                stanzas.append(stanza_text(cur))
                cur = []
            flush()
            title, stanzas = line.strip(), []
            continue
        if re.match(r"^ {3}\S", line):
            cur.append(line)
        elif cur:
            stanzas.append(stanza_text(cur))
            cur = []
    if cur:
        stanzas.append(stanza_text(cur))
    flush()
    return hymns


def parse_gerhardt():
    raw = read(WORKS["gerhardt"][2])
    lines = raw.split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip() == "SPIRITUAL SONGS" and i > 100)
    end = next(i for i, l in enumerate(lines) if "END OF THE PROJECT GUTENBERG" in l)
    hymns, title, cur, stanzas = [], None, [], []

    def flush():
        if title and stanzas:
            hymns.append(Hymn("gerhardt", stanzas[0].split("\n")[0], "gutenberg/pg30362.txt#%s" % title, list(stanzas)))

    for line in lines[start + 1:end]:
        if re.match(r"^ {8,}[A-Z][A-Z0-9 ,!'’.?;:()-]+$", line):
            if cur:
                stanzas.append(stanza_text(cur))
                cur = []
            if title and not stanzas and not cur:
                title += " " + line.strip()   # caps title wrapped onto a second line
            else:
                flush()
                title, stanzas = line.strip(), []
            continue
        if re.match(r"^ {4,}\S", line) and title:
            if not cur and re.search(r"\b[IVXLCivxlc]+\.\s*\d", line):
                continue  # scripture epigraph ("Isa. liii. 4-7; John i. 29.")
            cur.append(line)
        elif cur:
            stanzas.append(stanza_text(cur))
            cur = []
    if cur:
        stanzas.append(stanza_text(cur))
    flush()
    return hymns


def parse_toplady():
    raw = read(WORKS["toplady"][2])
    lines = raw.split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("rock of ages cleft"))
    couplets, cur = [], []
    for line in lines[start:]:
        if "END OF THE PROJECT GUTENBERG" in line or line.strip().startswith("A. M. Toplady"):
            break
        if re.match(r"^  \S", line):
            cur.append(line)
        else:
            if cur:
                couplets.append(cur)
                cur = []
    if cur:
        couplets.append(cur)
    # the booklet prints one couplet per illustrated page; the hymn's stanzas are six lines
    stanzas = []
    for k in range(0, len(couplets), 3):
        group = [l for c in couplets[k:k + 3] for l in c]
        stanzas.append(stanza_text(group))
    return [Hymn("toplady", "Rock of ages", "gutenberg/pg26874.txt", stanzas)]


def parse_havergal():
    raw = read(WORKS["havergal"][2])
    lines = raw.split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("Take my life, and let it be"))
    couplets, cur = [], []
    for line in lines[start:]:
        if re.match(r"^ {4}\S", line):
            cur.append(line)
        else:
            if cur:
                couplets.append(cur)
                cur = []
            if couplets and len(couplets) >= 12:
                break
    couplets = couplets[:12]
    # Havergal wrote the hymn in couplets; hymnals sing it in four-line stanzas
    stanzas = [stanza_text(couplets[k] + couplets[k + 1]) for k in range(0, 12, 2)]
    return [Hymn("havergal", "Take my life", "gutenberg/pg31647.txt#Take my life", stanzas)]


def parse_openhymnal():
    hymns = []
    for path in sorted(glob.glob(os.path.join(SOURCES, "openhymnal", "Complete", "*", "*.abc"))):
        raw = read(os.path.relpath(path, SOURCES))
        wl = [l[2:] for l in raw.splitlines() if l.startswith("W:")]
        if not wl:
            continue
        pd = any(re.search(r"^C:.*copyright:\s*public domain", l, re.I) for l in raw.splitlines())
        stanzas, numbers, cur, num = [], [], [], None
        for l in wl:
            if not l.strip():
                if cur:
                    stanzas.append(stanza_text(cur))
                    numbers.append(num)
                cur, num = [], None
                continue
            m = re.match(r"\s*(\d+)\.\s*(.*)$", l)
            if m:
                if cur:
                    stanzas.append(stanza_text(cur))
                    numbers.append(num)
                cur, num = [m.group(2)], int(m.group(1))
            else:
                cur.append(l)
        if cur:
            stanzas.append(stanza_text(cur))
            numbers.append(num)
        d = os.path.basename(os.path.dirname(path))
        h = Hymn("openhymnal", d, os.path.relpath(path, os.path.join(SOURCES, "openhymnal")), stanzas, [n or (k + 1) for k, n in enumerate(numbers)])
        h.public_domain = pd
        h.title = next((l[2:].strip() for l in raw.splitlines() if l.startswith("T:")), d.replace("_", " "))
        hymns.append(h)
    return hymns


# ---------------------------------------------------------------------------

def title_from(first_line):
    t = first_line.strip().strip("[]").rstrip(" .,;:!?-—")
    t = re.sub(r"\s*\(.*?\)\s*", " ", t).strip() if t.count("(") == t.count(")") and "(" in t else t
    words = t.split(" ")
    # printers' convention: the first word (or two) in small caps
    fixed = []
    for k, w in enumerate(words):
        if k < 2 and len(w) > 1 and w.isupper() and w not in ("O", "GOD", "LORD"):
            w = w[0] + w[1:].lower()
        elif k < 2 and w in ("GOD", "LORD"):
            w = w.title()
        fixed.append(w)
    return " ".join(fixed)


def find_hymn(hymns, source, locator):
    loc = locator.lower()
    for h in hymns:
        if h.source != source:
            continue
        if source in ("wesley", "openhymnal", "keble", "toplady", "havergal"):
            if h.locator.lower() == loc:
                return h
        else:
            fl = re.sub(r"[^a-z0-9 ]", "", (h.locator or "").lower())
            lq = re.sub(r"[^a-z0-9 ]", "", loc)
            if fl.startswith(lq):
                return h
    return None


def pick_stanza(h, pick):
    if isinstance(pick, int):
        if pick in h.numbers:
            k = h.numbers.index(pick)
            return k, h.stanzas[k]
        return None, None
    p = re.sub(r"[^a-z0-9 ]", "", pick.lower())
    for k, s in enumerate(h.stanzas):
        fl = re.sub(r"[^a-z0-9 ]", "", s.split("\n")[0].lower())
        if fl.startswith(p):
            return k, s
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    hymns = []
    for fn in (parse_watts, parse_olney, parse_wesley, parse_keble, parse_gerhardt, parse_toplady, parse_havergal, parse_openhymnal):
        try:
            got = fn()
        except FileNotFoundError as e:
            print("missing source for %s: %s" % (fn.__name__, e))
            got = []
        hymns.extend(got)
        if args.verbose:
            print("%-18s %4d hymns" % (fn.__name__, len(got)))

    entries, problems = [], []
    per_author, per_hymn, seq = {}, {}, {}
    for pick in PICKS:
        source, locator, slug, year, picks = pick[:5]
        translator = pick[5] if len(pick) > 5 else None
        name, died = AUTHORS[slug]
        if died >= PD_CUTOFF:
            problems.append("%s: author %s died %d (not public domain)" % (locator, name, died))
            continue
        if translator and TRANSLATORS[translator][1] >= PD_CUTOFF:
            problems.append("%s: translator not public domain" % locator)
            continue
        h = find_hymn(hymns, source, locator)
        if h is None:
            problems.append("%s/%s: hymn not found" % (source, locator))
            continue
        if source == "openhymnal" and not getattr(h, "public_domain", False):
            problems.append("%s: abc file lacks a 'copyright: public domain' line" % locator)
            continue
        if source == "olney" and h.author_hint and name.split()[-1] not in h.author_hint:
            problems.append("%s: Olney attributes this hymn to %s, not %s" % (locator, h.author_hint, name))
            continue
        voice = name + (" (tr. %s)" % TRANSLATORS[translator][0] if translator else "")
        work, srcslug, _ = WORKS[source]
        if source == "openhymnal":
            work = "%s (%d), Open Hymnal Project edition" % (h.title, year)
        hymn_title = title_from(h.first_line() if source != "keble" else h.locator.rstrip("."))
        if source == "openhymnal":
            hymn_title = h.title
        for p in picks:
            k, text = pick_stanza(h, p)
            if text is None:
                problems.append("%s: stanza %r not found" % (locator, p))
                continue
            n = h.numbers[k]
            if len(text) > MAX_CHARS:
                problems.append("%s st. %d: %d chars > %d, skipped" % (locator, n, len(text), MAX_CHARS))
                continue
            if per_author.get(slug, 0) >= MAX_PER_AUTHOR:
                problems.append("%s st. %d: per-author cap (%d) reached for %s" % (locator, n, MAX_PER_AUTHOR, name))
                continue
            if per_hymn.get((source, locator), 0) >= MAX_PER_HYMN:
                problems.append("%s st. %d: per-hymn cap reached" % (locator, n))
                continue
            per_author[slug] = per_author.get(slug, 0) + 1
            per_hymn[(source, locator)] = per_hymn.get((source, locator), 0) + 1
            seq[slug] = seq.get(slug, 0) + 1
            entries.append({
                "id": "hym-%s-%03d" % (slug, seq[slug]),
                "kind": "hymn",
                "ref": "%s (%d), st. %d" % (hymn_title, year, n),
                "text": text,
                "voice": voice,
                "insight": "",
                "witness": {"voice": voice, "work": work, "source": srcslug, "path": h.path_frag, "quote": ""},
                "themes": [],
                "added": ADDED,
            })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("wrote %d hymn stanzas -> %s" % (len(entries), os.path.relpath(args.out, ROOT)))
    print("\nper author:")
    for slug, n in sorted(per_author.items(), key=lambda kv: -kv[1]):
        print("  %-28s %3d" % (AUTHORS[slug][0], n))
    if problems:
        print("\nnotes (%d):" % len(problems))
        for p in problems:
            print("  - " + p)


if __name__ == "__main__":
    main()
