# Licenses and attributions

The plugin code is MIT (see [LICENSE](LICENSE)). The corpus in
`plugins/while-you-wait/data/devotionals.json` quotes Scripture and other
texts under the terms below. `scripts/validate-corpus.py` enforces the
per-translation verse budgets, counted in verses (not entries) via each
entry's ref range.

## Scripture translations

Copyright notices are reproduced exactly as each publisher requires. Verse
limits are the publisher's "no written permission needed" thresholds as
published on the pages cited; the plugin's own budgets sit below them.

### ESV (Crossway)

Scripture quotations are from the ESV® Bible (The Holy Bible, English Standard Version®), © 2001 by Crossway, a publishing ministry of Good News Publishers. ESV Text Edition: 2025. The ESV text may not be quoted in any publication made available to the public by a Creative Commons license. The ESV may not be translated in whole or in part into any other language. Used by permission. All rights reserved.

- Publisher limit: up to 500 verses, not exceeding 25% of the work, nor 50% of any one book of the Bible.
- Plugin budget: 450 target, 500 hard cap (frozen; see docs/PLAN-0.5.md).
- Source: https://www.crossway.org/permissions/

### NLT (Tyndale House)

Scripture quotations marked (NLT) are taken from the Holy Bible, New Living Translation, copyright ©1996, 2004, 2015 by Tyndale House Foundation. Used by permission of Tyndale House Publishers, Carol Stream, Illinois 60188. All rights reserved.

- Publisher limit: up to 500 verses, not exceeding 25% of the work, not a complete book.
- Plugin budget: 450 hard cap.
- Source: https://www.tyndale.com/permissions

### CSB (Holman Bible Publishers)

Scripture quotations marked CSB have been taken from the Christian Standard Bible®, Copyright © 2017 by Holman Bible Publishers. Used by permission. Christian Standard Bible® and CSB® are federally registered trademarks of Holman Bible Publishers.

- Publisher limit: up to 1,000 verses, not exceeding 50% of the work, not a complete book.
- Plugin budget: 700 hard cap.
- Source: https://csbible.com/permissions/

### AMP (The Lockman Foundation)

Scripture quotations taken from the Amplified® Bible (AMP), Copyright © 2015 by The Lockman Foundation. Used by permission. www.Lockman.org

- Publisher limit: up to 1,000 verses, not exceeding 50% of the work, not a complete book; no more than 1,000 verses stored in an electronic retrieval system.
- Plugin budget: 150 hard cap.
- Source: https://www.lockman.org/permission-to-quote-copyright-trademark-information/

### KJV (King James Version)

The King James Version (1611/1769 text) is in the public domain in the United
States and worldwide, with the exception of the United Kingdom, where the
Crown holds perpetual rights administered by Cambridge University Press. No
verse limit applies in the corpus.

### WEB (World English Bible)

The World English Bible is dedicated to the public domain by its editors
(eBible.org). "World English Bible" is a trademark; the text itself may be
quoted freely. No verse limit applies in the corpus.

### ASV (American Standard Version)

The American Standard Version (1901) is in the public domain. No verse limit
applies in the corpus.

### YALL (Y'all Version)

YALL: pending written permission from John Dyer (yallversion.com)

The validator refuses YALL entries until the line above is replaced with one
that starts with `YALL:` and no longer says "pending".

## Other corpus content

- **Quotes** are short excerpts from published works, attributed to author and
  work in each entry (`voice`, `ref`). `source: "primary"` means the wording
  was checked against the work itself; `"attributed"` means it circulates
  under that author's name but has not yet been verified against a primary
  source.
- **Creeds, catechisms, hymns, and prayers** shipped in the corpus are
  public-domain texts (historic creeds and confessions; hymn stanzas by Watts,
  Wesley, Newton, Cowper, Havergal, Crosby, Toplady, Luther, and others).
- **Insights** quote commentators whose works are public domain (CCEL and
  similar corpora); each witness names the underlying author and work in the
  entry's `witness` object.
