# Labelling guide (M0 + M2 combined)

Purpose: build the human answer key used to evaluate extraction (recall/precision) and retrieval (hit rate). This is ground truth. It must come from reading the source, never from the system's own output.

Order: 202409 pushbacks (held out), 201804 evictions, 202110 returns. Then, if time allows, the two education reports.

## One file per report

`eval/gold/<document_id>.yaml`, copied from `eval/gold/TEMPLATE.yaml`. Edit in VS Code (plain text, UTF-8). Do not use Excel.

## What counts as a recommendation

An explicit request for action addressed to a named actor, normally in the report's recommendations section. Include it only if you could finish the sentence "HRW asks <actor> to ...". Background findings and descriptions are not recommendations.

## Rules

1. **Verbatim.** Copy the exact words from the PDF, including punctuation. Do not fix typos, merge lines or paraphrase.
2. **Record artefacts.** If copying from the PDF produces glued footnote numbers, odd hyphenation, or a header in the middle of the text, keep what you copied and describe it in `notes`. These notes become the M1 test cases.
3. **Actor as written.** `target_actor_as_written` is the heading or phrase in the source (e.g. the "To ..." heading). Do not normalise it.
4. **Page.** Record the PDF page number so any label can be checked.
5. **Edge cases go in `notes`, not in your head.** Examples: a recommendation split into sub-bullets, one sentence addressed to several actors, a recommendation in the body text instead of the recommendations section. We decide the pattern after seeing two reports. Do not invent a rule early.

## Precedent links (only fill in when you actually see one)

`precedent_of` lists earlier recommendations (other reports) that this one repeats or evolves. Use the tiers below, and quote the earlier text verbatim with its report id and page.

| Tier | Meaning |
|---|---|
| `same_actor_same_ask` | Same addressee, same requested action, possibly reworded |
| `same_actor_different_ask` | Same addressee, different requested action on the same issue |
| `same_issue_different_actor` | Same issue and similar ask, different addressee |
| `none` | No precedent in the corpus |

Also write `difference`: one factual sentence, e.g. "2024 wording adds Cyprus as an actor; 2018 text names only municipalities". If you cannot say how they differ, they may not be a pair.

## Time box

Aim for about 45 minutes per report. If a report has far more recommendations than expected, label only the first 15 and say so in the file header, so recall can be measured on a defined subset.
