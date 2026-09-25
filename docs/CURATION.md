# How the corpus is curated

*while you wait* puts a sentence of Scripture, confession, hymn, or theology in
front of a Christian every time they press enter. A wrong word in that box is
worse than an empty box. This page explains what we did to earn the right to
show it, and what every future entry has to pass.

## The problem we found in 0.4.1

Before expanding the corpus we red-teamed the one we had. The audit
(`docs/audit/redteam-0.4.1.md`) classified all 305 theologian quotes and
spot-checked 60 verses against the published translations. The results:

| finding | count |
|---|---|
| quotes fabricated (no trace in the cited work or anywhere) | 23 |
| quotes misattributed (the words belong to someone else) | 12 |
| paraphrases presented inside quotation marks | 121 |
| verses with word-level deviations in a 60-verse sample | 7 |

Some carried confident, checkable citations that do not exist: a Spurgeon
sermon dated 1861, a *Morning and Evening* reading for August 11, a Manton
sermon on Psalm 23. That is what a language model does when asked to recall a
quotation. It is also why the new pipeline never asks a model to recall one.

## Three rules

1. **Primary text is never written by a model.** Scripture, catechism answers,
   creeds, hymn stanzas, and quotations are copied verbatim from a source we
   can point to, and a script proves it (see *Witnesses* below). Nothing in
   `text` is paraphrased, tidied, or "improved". A partial verse is labelled
   with an a/b suffix; an ellipsis is never allowed.
2. **Commentary is grounded in a human voice.** The one- or two-sentence
   `insight` under a verse leads with a verbatim line, forty words or fewer,
   from a real commentator in an open corpus (Augustine, Chrysostom, Calvin,
   Matthew Henry, Spurgeon's *Treasury of David*), then turns to the reader.
   The line is machine-verified against the source file before the entry can
   merge.
3. **Everything is checked by a machine, then by an adversary.** Every entry
   passes `validate-corpus.py` (schema, ids, refs against a 66-book table,
   translation budgets, theme vocabulary, length, spoofing characters,
   duplicates) and `verify-witness.py` (verbatim presence in the source).
   Every generated batch is then read by an independent reviewer whose job is
   to find what is wrong, and whatever it flags is rewritten before merge.

## Witnesses

Every entry that came through the new pipeline carries a `witness`:

```json
"witness": {
  "voice": "Charles Spurgeon",
  "work": "Morning and Evening, October 7 (morning)",
  "source": "https://ccel.org/ccel/s/spurgeon/morneve/cache/morneve.txt",
  "path": "web/3f1c…txt",
  "quote": "It is a poor faith which can only trust God when friends are true"
}
```

`scripts/verify-witness.py --fetch` downloads the source once into the
git-ignored `sources/` directory and requires `quote` to appear in it. For
scanned books it tolerates OCR noise with a similarity floor of 0.95 and reports
those matches as fuzzy. For catechisms and hymns the whole `text` must appear in
the source. CI runs this on every push, so a quotation that cannot be re-fetched
and re-found by a stranger cannot ship.

Sources used, all public domain or explicitly licensed, are listed in
`docs/SOURCES.md`. Verbatim excerpts from copyrighted modern authors are kept
under fifty words with attribution, which is ordinary fair use for commentary.

## Scripture

Verse text is checked against the published translation, not typed from
memory. The KJV is compared programmatically to a public-domain text; the ESV
is compared to Crossway's text via their API (`scripts/check-scripture.py`,
`ESV_API_KEY`). Each translation stays inside its publisher's quotation limit,
enforced by the validator: ESV 500 verses, NLT 500, CSB 1,000, AMP 1,000.
Required credit lines are in `LICENSES.md`.

## What the process changed in the original 804 entries

The 0.5.0 corpus has 1,682 entries: 499 scripture, 289 quotes, 701 creeds and catechisms, 193 hymn stanzas. Of these, 1,138 carry a witness that CI re-verifies against its source; the rest are the original scripture entries, which are checked against the published translations instead.

| | 0.4.1 | 0.5.0 |
|---|---|---|
| quotes kept word for word | | 58 |
| quotes corrected to the real wording or replaced with a verified line by the same author | | 231 |
| quotes dropped as unverifiable | | 16 |
| quotes with a verified primary source and witness | 0 | 244 |
| scripture texts corrected to the published translation | | 187 of 499 |

Four modern works could not be verified online at all (Ferguson, *In Christ
Alone* and *Devoted to God*; Murray, *Principles of Conduct*; one Elisabeth
Elliot line with no printed source). Those quotes were replaced with verified
lines from other works by the same authors.

## How new material is generated

Each wave runs as a pipeline, one batch at a time:

1. **Seed.** The primary text is ingested verbatim from its source
   (`scripts/ingest-creeds.py`, `scripts/ingest-hymns.py`) or the verse is
   chosen by reference and its commentary candidates pulled from
   `sources/index.json`, an index of 159,000 commentary passages keyed by
   verse.
2. **Write.** A writer receives the text, the witness candidates, and the house
   rules, and writes only the insight and themes. It cannot touch the text.
3. **Verify.** The validator and the witness verifier run on the batch file.
4. **Red team.** A separate reviewer reads every insight looking for
   misreadings, unverifiable claims, invented quotations, missing application,
   theological imprecision, and formula. Flagged entries are rewritten and
   re-verified.
5. **Audit.** A reviewer who has seen none of the above samples the finished
   wave at random and rules on whether it is fit to ship.
6. **Merge.** `scripts/merge-incoming.py` appends the batch, the full gate runs
   again, and the plugin version is bumped so installed copies see the update.

Every change to the corpus, including the remediation of 0.4.1, was applied
through reviewed patch files under `corpus/fixes/`, each operation carrying its
evidence. Nothing was edited by hand.

## Why it is built this way

The renderer is a single Python file with no dependencies and no network
access. The hook wrapper emits exactly one JSON object with one key or nothing
at all, so a corpus entry can never reach the model's context. The verifier,
validator, and patch applier are each under three hundred lines of standard
library. The heavy machinery, the source clones and the commentary index, stays
out of the repository and can be rebuilt from public URLs by anyone. What ships
is a JSON file whose every line can be traced to a page someone can open.
