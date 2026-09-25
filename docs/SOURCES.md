# Witness and primary-text sources

Everything under `sources/` is a local, gitignored clone or download. Nothing
in it is redistributed by this repo; the corpus carries only short excerpts
(insight lines of at most 40 words) or public-domain primary text (creeds,
catechisms, hymn stanzas), each pointing back to the exact file it came from
through `witness.source` + `witness.path`. `scripts/verify-witness.py` refuses
any entry whose text cannot be found verbatim in that file.

Attribution in the rendered entry always names the underlying author and
work (e.g. "John Chrysostom, Homilies on 1 Corinthians"), never the repo.
`witness.source` is the repo slug or site path for provenance only.

## Sources

| source (`witness.source`) | URL | license | what we take | `witness.path` is relative to |
|---|---|---|---|---|
| `HistoricalChristianFaith/Commentaries-Database` | https://github.com/HistoricalChristianFaith/Commentaries-Database | repo carries no license file; texts are public-domain CCEL / pre-1930 translations, except the excluded authors below | verse-keyed `[[commentary]]` quotes (insight witness lines) | `sources/Commentaries-Database/` — e.g. `John Chrysostom/1 Corinthians 10_1-5.toml` |
| `lyteword/chspurgeon-tod` | https://github.com/lyteword/chspurgeon-tod | CC0 1.0 (repo LICENSE); text public domain (Spurgeon d. 1892) | Spurgeon's Exposition per verse; the "Explanatory Notes" quotations, attributed to the author Spurgeon names | `sources/chspurgeon-tod/` — e.g. `volume-1/psalm-23.md`, `volume-6/psalm-119/verses-105-112.md` |
| `revisedcommonversion/matthew-henry-commentary` | https://codeberg.org/revisedcommonversion/matthew-henry-commentary | CC0 1.0 (repo LICENSE, "This text is in the Public Domain") | `### Verses a-b` sections (indexed per verse, `granularity: range`) and chapter introductions (`granularity: chapter`) | `sources/matthew-henry-commentary/` — e.g. `psalms/MHC - Psalm 023.md` |
| `ccel.org/ccel/calvin` | `https://ccel.org/ccel/c/calvin/calcom<NN>/cache/calcom<NN>.txt` (each file's header says `Rights: Public Domain`) | public domain (Calvin Translation Society editions, 1840s-50s) | Calvin's comment on each verse (split at the verse leaders inside each range section) | `sources/` — e.g. `ccel/calvin/calcom38.txt` |
| `NonlinearFruit/Creeds.json` | https://github.com/NonlinearFruit/Creeds.json | Unlicense for the repo, except 8 copyrighted documents (see exclusions) | whole creeds, catechism Q&As, confession sections as `kind: creed` primary text | `sources/Creeds.json/` — e.g. `creeds/heidelberg_catechism.json#32` |
| `gutenberg.org/ebooks/13341` | https://www.gutenberg.org/ebooks/13341 | public domain (Watts d. 1748); Project Gutenberg License applies only to the PG header/trademark, which we do not reproduce | Watts, *Hymns and Spiritual Songs* stanzas | `sources/` — `gutenberg/pg13341.txt#Hymn 3:7` |
| `gutenberg.org/ebooks/4272` | https://www.gutenberg.org/ebooks/4272 | public domain (Keble d. 1866) | Keble, *The Christian Year* stanzas | `sources/` — `gutenberg/pg4272.txt#Morning.` |
| `gutenberg.org/ebooks/30362` | https://www.gutenberg.org/ebooks/30362 | public domain (Gerhardt d. 1676; translator John Kelly d. 1890, 1867 edition) | Gerhardt, *Spiritual Songs* stanzas | `sources/` — `gutenberg/pg30362.txt#<CAPS TITLE>` |
| `gutenberg.org/ebooks/26874` | https://www.gutenberg.org/ebooks/26874 | public domain (Toplady d. 1778; 1909 US printing, copyright expired) | "Rock of Ages", 4 stanzas | `sources/` — `gutenberg/pg26874.txt` |
| `gutenberg.org/ebooks/31647` | https://www.gutenberg.org/ebooks/31647 | public domain (Havergal d. 1879) | "Take My Life" from *Kept for the Master's Use*; her couplets are paired into the sung four-line stanzas | `sources/` — `gutenberg/pg31647.txt#Take my life` |
| `ccel.org/ccel/newton/olneyhymns` | https://ccel.org/ccel/n/newton/olneyhymns/cache/olneyhymns.txt (`Rights: Public Domain`) | public domain (Newton d. 1807, Cowper d. 1800; 1779 facsimile) | Olney Hymns stanzas, attributed per the file's author line | `sources/` — `ccel/newton-olneyhymns.txt#Book I, Hymn 41` |
| `ccel.org/w/wesley/hymn` | https://ccel.org/w/wesley/hymn/jw.html (index) and `jwgNN/jwgNNNN.html` pages | public domain (Charles Wesley d. 1788; 1889 printing of the 1780 Collection) | selected hymn pages saved locally; numbered stanzas | `sources/` — `ccel/wesley/jwg0201.html` |
| `mzealey/openhymnal` | https://github.com/mzealey/openhymnal (mirror of openhymnal.org) | per-file: only files whose `C:` line reads `copyright: public domain` are used; the project's own content is public domain | the plain-text `W:` stanza blocks (later stanzas only; the earlier stanzas are syllable-split under the music and are not taken) | `sources/openhymnal/` — `Complete/Abide_With_Me/Abide_With_Me-Eventide.abc` |

`sources/index.json` (built by `scripts/index-witnesses.py`) maps every single
verse ("Psalm 23:1") or chapter ("Psalm 23") to its candidates from the first
four sources. Each candidate carries `granularity`: `verse`, `range` (the
source comments on a span that includes this verse; `range` gives the span)
or `chapter`.

## Exclusion rules

* **Commentaries-Database authors not in the public domain** are never
  indexed: `CS Lewis`, `JRR Tolkien`, `GK Chesterton`, `Douglas Wilson`, plus
  any author whose `metadata.toml` `default_year` is after 1900 (the repo's
  `9999` marks undatable Pseudo-* Fathers and is allowed). `JB Lightfoot`
  (d. 1889), `John Wesley`, `John Calvin`, `Martin Luther` and the Fathers
  stay in. Directories named after Bible books (`Acts/`, `Romans/`, ...) hold
  Scripture quoting Scripture and are skipped as witness voices.
  Apocryphal books (Sirach, Wisdom, Maccabees, ...) are not indexed.
* **Creeds.json**: only documents whose `Metadata.SourceAttribution` is
  exactly `Public Domain`, and never these eight copyrighted files:
  `chicago_statement_on_biblical_inerrancy`, `christ_hymn_of_colossians`,
  `christ_hymn_of_philippians`, `christian_shema`, `confession_of_peter`,
  `helvetic_consensus`, `savoy_declaration`, `shema_yisrael`. Documents whose
  attribution names a translator ("Public Domain - Translated by ...") are
  not ingested either. Items longer than 700 characters are skipped and
  reported.
* **Hymns**: only writers and translators who died before 1930 (the table in
  `scripts/ingest-hymns.py`). Open Hymnal files whose lyrics carry a modern
  copyright (Dumont, Penney, Robertson, ...) or a modern translation are not
  used. Stanzas over 420 characters, more than 6 per hymn or more than 25 per
  author are dropped.
* **Verbatim rule**: primary text is copied as-is. The only changes are
  whitespace normalization and removal of editorial markup that is not text
  (Gutenberg `_italics_`, Watts' omission brackets, abc soft hyphens `\-`,
  Gutenberg `[Illustration: ...]` markers). Catechism entries are framed
  `Q. <question> A. <answer>`; the verifier checks the two halves separately.

## Wanted but not available here

* Thirty-Nine Articles, Augsburg Confession, Luther's Small Catechism: not in
  Creeds.json. Wave 1 fills the 700 creed entries from WCF, Belgic, Dort and
  the 1689 LBC instead.
* Bonar, Crosby, Lyte (beyond "Abide with Me"), Neander: no trustworthy
  plain-text public-domain source found on GitHub/Gutenberg/CCEL in this
  pass (Internet Archive OCR only). Crosby's later hymns (post-1929
  publications) would need per-hymn checking anyway.
* More Calvin volumes follow the same CCEL URL pattern (`calcom01`-`calcom45`);
  only Genesis, Psalms, Isaiah, John, Romans and Hebrews are downloaded.
