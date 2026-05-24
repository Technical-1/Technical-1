# Languages-by-LOC SVG widget — design

**Date:** 2026-05-24
**Author:** brainstormed with Claude

## Goal

Add a second 850×255 SVG below the existing stats SVG showing the user's top programming languages by lines of code. Visually indistinguishable in framing, palette, typography, and ASCII-art layout from `compact/dark_mode_simple.svg` / `compact/light_mode_simple.svg`.

## Files

**New:**
- `compact/dark_mode_languages.svg`
- `compact/light_mode_languages.svg`
- `cache/<user-hash>_langs.txt` — sidecar cache, one row per language, derived entirely from the main cache and rewritten on each successful run.

**Modified:**
- `scripts/today.py` — extend `loc_query` GraphQL with `primaryLanguage { name color }`, compute per-language buckets in `cache_builder` (or a sibling helper), render the new SVGs in a new `render_languages_svg()` function called from `main()`.
- `README.md` — add a second `<picture>` block immediately under the existing one, dark/light handled identically.

## Visual specification

Frame: 850×255 px, dark bg `#161b22`, 15px corner radius, Consolas/monospace 16px — identical to the existing compact SVG.

Layout:
- ASCII-art panel reused on the left (`<g transform="translate(5, 0) scale(0.5)">`).
- Right panel single section header: `- Languages by LOC ————…` mirroring the dash-line style of the existing "GitHub Stats" header.
- Top 6 languages by user-authored additions, rank 7+ collapsed into one "Other" row (max 7 rows total).
- Row template: `. <name>   <bar> <abbreviated_count> (<percent>%)` with dot-leader spacing matching the existing rows.
- Bar: Unicode full-block (`█`) repeated. Top language gets exactly 20 blocks; each other language gets `max(1, floor(20 * additions / top_additions))` blocks.
- Label color (`<name>`): existing `.key` orange (`#ffa657`).
- Count color: existing `.value` blue (`#a5d6ff`).
- Percent color: existing `.cc` gray (`#616e7f`).
- Bar color: GitHub's `primaryLanguage.color` per language (e.g. Python `#3572A5`, Go `#00ADD8`). For "Other" use `.cc` gray. This is the deliberate one departure from the strict 4-color palette: language-recognition value outweighs strict cohesion, and every other element stays in palette.

Light-mode variant: same layout, palette swapped via the same conventions as `compact/light_mode_simple.svg`.

## Data flow

1. `loc_query` GraphQL query gets `primaryLanguage { name color }` added to the per-repo node selection — no extra API call, just one new field.
2. After `cache_builder` has updated per-repo LOC, a new aggregator walks the (filtered, non-fork) edges + cached additions and produces a `dict[language_name, (color, total_additions)]`.
3. Top 6 by additions kept; remainder summed into a single "Other" bucket with no color (rendered in `.cc` gray).
4. Result serialized to the sidecar cache file in deterministic order (rank ascending) for human-readable debugging.
5. `render_languages_svg()` reads the aggregated dict, computes bar widths and percentages, emits one `<tspan>` per row, writes `compact/dark_mode_languages.svg` and `compact/light_mode_languages.svg`.

Forks are already excluded by the existing `filter_owned_forks` helper before `cache_builder` runs, so no double-count.

## Sidecar cache format

`cache/<user-hash>_langs.txt`, one row per language, rank-ordered:

```
<rank> <language_name> <hex_color_no_hash> <additions>
```

`<language_name>` may contain spaces (e.g. "Jupyter Notebook"); since rank, color, and additions are all `\S+`, split with `maxsplit=3` from the right side of the row, or quote the name. Implementation choice: quote the name as `"Jupyter Notebook"` so the split is unambiguous.

## Bar-width calculation

```
top = max(additions across all kept languages)
for each language:
    bar_blocks = 20 if language is top else max(1, floor(20 * additions / top))
```

Percent: `round(100 * additions / total_additions_across_all_kept_languages, 0)`. Percentages may sum to 99% or 101% due to rounding; that's acceptable on a personal stat panel.

## Edge cases

- **Repo with null `primaryLanguage`** (no code detected, or unusual content): skip from the language buckets. The repo's LOC still appears in the existing total LOC widget but not in the languages chart.
- **Zero total additions across all repos**: render the section header but replace the rows with a single `. (no language data)` row in `.cc` gray. Don't draw bars.
- **First run after deploy** (sidecar doesn't exist yet): created on demand. No special initialization needed.

## Workflow / CI impact

None. Same `build.yaml`, same daily cron, same commit step. The new SVG files get `git add .`'d alongside the existing ones, and the sidecar cache likewise.

## Testing

- One end-to-end workflow run after merge, visually inspect both SVGs in a browser.
- Verify percentages sum to 100% ±1% on the rendered chart.
- Verify `sum(language_additions_in_sidecar) == sum(additions_for_repos_with_non_null_primaryLanguage)` so the aggregation is self-consistent.
- Confirm the README's GitHub-rendered preview shows both SVGs stacked vertically, with prefers-color-scheme switching working for both.

## Non-goals (YAGNI)

- Per-byte language breakdown via `Repository.languages` connection — extra API calls, marginal accuracy gain.
- Interactive tooltips — requires embedded HTML, breaks GitHub's static SVG rendering.
- Trend over time — single snapshot only.
- Independent light-mode bar colors — GitHub's official language colors work in both light and dark modes.
- Configurable top-N count — hardcoded 6 keeps the implementation simple and the layout fixed.
