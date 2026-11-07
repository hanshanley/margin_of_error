# 2026 participation evidence batch 02

Corrected prepublication public-safe evidence batch assembled on 2026-11-07. It preserves unpublished draft 01 unchanged, retains the original six observations and Butler matrix, adds Harris County and California as the seventh and eighth typed observations, and restores Colorado's qualified native age/gender count composition and complete combined/mail/in-person native aggregate cells.

## Important interpretation limits

- Measures remain distinct: reported ballots cast, returned-and-processed ballots, counted ballots, roster voters, and current-record participation credits are not interchangeable.
- Colorado age and recorded-gender tables are count-only partitions of the same statewide returned-and-processed frame. No group denominator or turnout rate is supplied or inferred.
- Harris County's 1,392,280 counted ballots are distinct from 1,393,495 election-roster voters; the preliminary report lists pending/rejected and potentially addable mail/provisional categories.
- California's 10,098,551 is retained only under the native voterTurnout label. The printed 43.4% is not automatically qualified, and the separate mode snapshot's accepted-total arithmetic conflict remains unresolved.
- No blended national total or unqualified turnout rate is supplied.
- No voter-person file, identifier, name, date of birth, address, candidate-choice payload, private fine cell, or unlicensed source presentation is included.

## Verify

```sh
python3 verify_batch.py
```

The verifier checks root and nested checksums, all eight observation numerators and qualified denominators against aggregate outputs, county/mode reconciliations, both Butler credit marginals, Colorado's 8+4 composition totals and 4,982 native cells, Harris County's 13 aggregate rows, California's 58 county and 58 mode rows, public-safe exclusions, and the complete ZIP when it is available beside the extracted files.
