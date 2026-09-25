# while-you-wait: the road to 4,000

Revised 2026-09-24 after Matt's direction. Superseded ideas (user-selectable
translation, tiered coverage) are gone.

## Decisions made

| topic | decision |
|---|---|
| target size | 4,000 entries, "balanced" mix |
| composition | scripture 1,600 · quote 1,200 · creed/catechism 700 · prayer 300 · hymn 200 |
| translations | fixed per entry, no user switching; mix within publisher caps |
| translation budget | ESV 450 (frozen: cap 500, ~477 used) · NLT 450 · CSB 700 · AMP 150 · KJV/WEB fill the rest · YALL pending permission |
| primary text | Scripture, catechism answers, quotes, prayers, hymns are **never altered**. Verbatim only. |
| insight ("commentary") | humanized: leads with a verbatim line (≤40 words) from a real commentator in an open-source corpus, machine-verified against the source file, then one sentence of application in the plugin's voice |
| new kind | `hymn` (public-domain stanzas: Watts, Wesley, Newton, Cowper, Havergal, Crosby, Toplady, Luther) |
| YALL | Matt sends a permission email to John Dyer (draft prepared) |
| voice | Reformed-evangelical, unchanged |
| open question | Matt mentioned "pods". If that means podcast transcripts, only explicitly licensed feeds qualify. Unresolved. |

## Open-source witness corpora (verified 2026-09-24)

| repo | contents | license | use |
|---|---|---|---|
| HistoricalChristianFaith/Commentaries-Database | verse-keyed TOML, 200+ authors (Augustine, Chrysostom, Calvin, Bede, Bernard, Wesley…) | repo unlicensed; underlying texts CCEL public domain | scripture insights, all books |
| lyteword/chspurgeon-tod | Treasury of David, Markdown per Psalm | CC0 | Psalms insights |
| NonlinearFruit/Creeds.json | 43 creeds/catechisms as JSON with provenance | Unlicense except 8 copyrighted docs (excluded) | creed/catechism primary text |
| Matthew Henry (Codeberg mirror), Calvin commentaries (CCEL) | wave-2 additions | public domain | broaden witness pool |

Witness attribution always names the underlying author and work, not the repo.

## Schema v2

```json
{
  "id": "scr-1co-010-004",
  "kind": "scripture | quote | creed | prayer | hymn",
  "ref": "1 Corinthians 10:4",
  "translation": "NLT",                       // scripture only, fixed per entry
  "text": "…verbatim…",
  "voice": "1 Corinthians",
  "insight": "Chrysostom: …verbatim ≤40 words… Then one applied sentence.",
  "witness": {                                // optional; required for new scripture entries
    "voice": "John Chrysostom",
    "work": "Homilies on 1 Corinthians",
    "source": "HistoricalChristianFaith/Commentaries-Database",
    "path": "John Chrysostom/1 Corinthians 10_1-5.toml",
    "quote": "they were nothing profited by the enjoyment of so great a gift…"
  },
  "source": "primary | attributed",           // quotes only
  "themes": ["christology", "perseverance"],   // controlled vocab, data/themes.json
  "added": "0.6.0"
}
```

`witness.quote` is the exact substring the verifier must find in the source file
(whitespace- and punctuation-normalized). Entries whose witness fails verification
cannot merge.

## Tooling to build (phase 0, release 0.5.0)

1. `scripts/migrate-v2.py`: assign ids, map old themes to the controlled vocab, keep
   everything else byte-identical. Fix the 9 duplicate refs.
2. `scripts/validate-corpus.py` v2: ids unique; refs parse; translation budgets at 90%
   of cap; per-voice cap 15; themes in vocab; hymn kind; `witness` shape; length bounds
   (text ≤ 420 chars, insight 120–360).
3. `scripts/verify-witness.py`: for each entry with `witness`, load the source file
   from `sources/` (gitignored clones) and confirm `witness.quote` appears verbatim.
4. `scripts/index-witnesses.py`: build `sources/index.json` mapping ref → candidate
   passages (author, work, path, first 600 chars) so generation batches can be seeded
   with real material instead of asking a model to remember it.
5. `scripts/ingest-creeds.py`: emit creed/catechism entries straight from Creeds.json
   (public-domain docs only), text verbatim, insight left blank for the humanize pass.
6. Renderer: `hymn` color, anti-repeat window 3% of corpus, least-seen picker in
   `${CLAUDE_PLUGIN_DATA}/state.json`.
7. `LICENSES.md` with each publisher's required attribution line.

## Generation pipeline per wave (~500 entries each, 7 waves)

1. **Seed**: pick refs/voices/documents for the wave; pull witness candidates from
   `sources/index.json`.
2. **Write**: subagent per batch of ~40 receives the primary text (verbatim, never to
   be edited), 3–5 witness candidates, and 6 existing entries as voice samples. It
   chooses one witness line ≤40 words and writes one application sentence.
3. **Verify**: `verify-witness.py` (mechanical), then a reviewer agent for theology and
   tone, then near-duplicate check against the corpus.
4. **Validate, bump `plugin.json` version, release.**

Wave order: 1 creeds/catechisms (700, mostly mechanical) + hymns (200) →
2 Psalms via Treasury of David → 3 Gospels + Epistles via patristics → 4 OT via Calvin/Henry
→ 5–6 quotes to 1,200 → 7 prayers + fill.

## Updates (unchanged from prior draft)

- Bump `plugin.json` version every release; README + first-run message tell users to
  enable marketplace auto-update.
- Live corpus channel: tag-triggered release publishes `devotionals.json` + manifest;
  SessionStart hook checks once/day, `updates: notify | auto | off`, default notify.

## Status (updated 2026-09-25)

Done:
- Red-team audit of 0.4.1 (`docs/audit/redteam-0.4.1.md`); all findings remediated through `corpus/fixes/*.json`.
- Schema v2, controlled themes, validator v2, witness verifier with URL fetch and OCR-tolerant matching, patch applier, merge tool, scripture checker, source fetch script, CI running the full gate, 37 unit tests.
- Hardening: wrapper emits one JSON object or nothing; atomic state; bidi/zero-width stripped; least-seen picker; hymn kind.
- Original 804 entries re-sourced: every quote verbatim with a witness (244), 187 verse texts corrected, 16 quotes dropped.
- Wave one staged and reviewed: 701 creeds/catechisms, 193 hymns; insights written, red-teamed in full, polished, and audited (defect rate in sample: 25% → 12% → pastoral-register only). Owner decided the reader is assumed to be a believer.
- Codex and Antigravity ports verified and updated for schema v2.

Decisions recorded: no user-selectable translation; balanced 4,000 mix; hymn kind; AMP ≤150; Luther Worms entry trimmed to the attested portion (Schaff); Heidelberg attribution hedged; Dort Fifth Head relabelled.

Next:
1. Merge wave one (→ 1,682), release 0.5.0.
2. Wave two: rewrite the original scripture and quote insights around witness lines from `sources/index.json` (66 still use the "Reformed X reads" template; 82% are third-person).
3. Waves three onward toward 4,000: scripture in NLT/CSB/KJV/WEB (ESV frozen), prayers (1662 BCP, Augustine, Anselm, Calvin, Luther), quotes to 1,200, YALL if permission arrives.
4. Update channel (release manifest + SessionStart check) and first-run message.
