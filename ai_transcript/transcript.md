# AI Conversation Transcript

This transcript captures the full AI-assisted journey behind Steam Games Insights,
from initial assignment understanding to final dashboard, data-quality hardening,
and expanded ETL test coverage.

The assistant used was GitHub Copilot (GPT-5.3-Codex) inside VS Code.

---

## 1. Understanding and breaking down the assignment

**Me:** Use the Steam gaming dataset to create an analytical dashboard about
gaming users. Extract raw data from an open-source Steam dataset. Use the raw
table containing details about the titles being played and the usage of these
titles.

**AI:** We can implement this with Python and Streamlit over an open-source,
keyless Steam data source, then structure it as ETL (`extract` / `transform` /
`quality`). The extract layer will pull raw title details and usage-related
fields, the transform layer will create analytical tables, and the dashboard
will present gaming-user insights.

**AI:** We will keep it reliable with explicit data-quality checks, offline unit
tests, a clear README, and this transcript.

---

## 2. Selecting the API and product direction

**Me:** Which Steam data source is free and keyless? The official Steam Web API
needs a key for many endpoints.

**AI:** Two practical options are the Steam storefront appdetails endpoint and
SteamSpy. Recommendation: SteamSpy, because it is keyless and provides analytics
fields such as reviews, owners estimates, concurrent users, prices, discounts,
and playtime, with genre/tags available via per-app enrichment.

**Me:** Verify the actual response shape first. I do not want to assume field
formats.

**AI:** Probed `request=top100in2weeks`: response is keyed by appid and includes
`positive`, `negative`, `owners` (range string), `price`, `initialprice`,
`discount`, and `ccu`. This base response does not include genre.

**AI:** Probed `request=appdetails&appid=<id>`: this adds `genre`, `tags`, and
`languages`.

**Me:** Genre requires per-app calls. How do we keep this fast?

**AI:** Two-step extract: fetch top list once, then enrich only top N titles
(default 50), throttled to approximately one request per second to stay
rate-limit friendly.

**Me:** Good. What should the product narrative be?

**AI:** A games-market analytics dashboard: what is played now (CCU), reception
vs audience size, pricing and discounts, genre-level distribution, and usage
trends.

---

## 3. ETL and data model design

**Me:** Define the model in a simple way. Create a clear table for the main
raw-title data, include extra columns created in transformation, and add a
summary table from raw data (for example, genre summary).

**AI:** The transform layer creates one detailed table and one summary table.

### Main table: `games`

| Column | Source field | Meaning |
| --- | --- | --- |
| `appid` | `appid` | Unique game id |
| `name` | `name` | Title name |
| `developer` | `developer` | Developer |
| `publisher` | `publisher` | Publisher |
| `ccu` | `ccu` | Concurrent users |
| `positive` | `positive` | Positive reviews |
| `negative` | `negative` | Negative reviews |
| `price_usd` | `price` | Current USD price |
| `initial_price_usd` | `initialprice` | Original USD price |
| `discount_pct` | `discount` | Discount percentage |
| `owners_min` | `owners` | Parsed minimum owners |
| `owners_max` | `owners` | Parsed maximum owners |
| `primary_genre` | `genre` | First genre token |
| `all_genres` | `genre` | Full genre string |
| `top_tags` | `tags` | Top-voted tags |

### Derived columns added in transform

| Derived column | Logic |
| --- | --- |
| `total_reviews` | `positive + negative` |
| `review_ratio` | `(positive / total_reviews) * 100` |
| `owners_mid` | `(owners_min + owners_max) / 2` |
| `avg_playtime_hours` | `average_forever / 60` |
| `median_playtime_hours` | `median_forever / 60` |
| `is_free` | `price_usd == 0` |
| `on_sale` | `discount_pct > 0` |
| `rating_label` | Positive, Mixed, Negative, or Insufficient data |

### Summary table: `genre_summary`

| Column | Meaning |
| --- | --- |
| `primary_genre` | Genre name |
| `games` | Number of games |
| `avg_review_ratio` | Average review ratio |
| `total_ccu` | Total concurrent users |
| `avg_price_usd` | Average price |
| `total_owners_mid` | Sum of owners midpoint |
| `free_games` | Count of free-to-play titles |

**Me:** The rating label should not mark a title as Positive on very low review
volume.

**AI:** Added a minimum-review threshold before assigning Positive/Mixed/Negative.
Otherwise, label is Insufficient data.

---

## 4. Dashboard evolution from simple to final

**Me:** Start with a simple analytical dashboard driven by raw and transformed
tables.

**AI:** Initial dashboard covered core visibility: games tracked, review quality,
concurrency, usage trends, and market split.

**Me:** Evolve this to a richer final dashboard with better navigation, filters,
and graph quality.

**AI:** Dashboard was expanded into multi-page analytics with left-side page
navigation and compact cross-page filters (title, publisher, country, date).

**Me:** Add executive growth metrics and improve storytelling.

**AI:** Added Usage Worldwide layer with engagement KPIs including MAU and DAU,
YoY deltas, sessions and hours trends, and month-over-month movement visuals.

**Me:** Include WAU in the metric narrative and keep extending insights.

**AI:** Captured WAU as a requested engagement metric in the dashboard evolution
requirements and retained MAU/DAU-driven growth narrative already implemented.

**Me:** Add AI-assisted summary to explain the charts.

**AI:** Added AI-generated summary blocks that compute narrative insights from
processed data (trend direction, market mix, top titles, genre signals,
free-vs-paid mix).

**Me:** Keep refining graph behavior and page-level readability.

**AI:** Final dashboard includes clearer chart grouping, top-title views,
country/genre breakdowns, usage-over-time visuals, and a dedicated data-quality
page plus data export view.

---

## 5. Data quality and reliability hardening

**Me:** How does data quality work? Is schema validation included?

**AI:** Initially it had rule-based checks (coverage, duplicates, ranges,
relationships). Then it was upgraded to include schema and key completeness
validation.

**Me:** Ensure schema of all fields is in place, keys are not null, and add
field-level checks with a full list.

**AI:** Implemented expanded quality checks in the processed layer.

### Final quality checks added

1. `non_empty`
2. `schema_columns_present`
3. `schema_types_valid`
4. `key_fields_not_null`
5. `game_coverage`
6. `no_duplicate_appids`
7. `names_present`
8. `reviews_non_negative`
9. `total_reviews_consistent`
10. `review_ratio_in_range`
11. `ccu_non_negative`
12. `price_valid`
13. `initial_price_valid`
14. `discount_price_relationship`
15. `discount_in_range`
16. `owners_non_negative`
17. `owners_min_le_max`
18. `owners_mid_in_bounds`

**AI:** Reliability posture also includes extraction retry/backoff and enrichment
failure isolation so one bad enrichment call does not drop an entire game row.

---

## 6. Test coverage expansion

**Me:** Do we have proper unit tests for the full ETL pipeline?

**AI:** Core transform/quality was covered, but full pipeline coverage needed
additional tests.

**Me:** Add tests for extract API failure, daily usage model, ETL orchestration,
and final processed-file validation.

**AI:** Added `tests/test_pipeline_layers.py` with:

1. `test_extract_api_failure_raises_extraction_error`
2. `test_usage_daily_model_outputs_expected_fields_and_ranges`
3. `test_usage_daily_model_is_deterministic_for_same_input`
4. `test_etl_run_orchestrates_layers_in_order`
5. `test_etl_run_returns_error_on_extract_failure`
6. `test_pipeline_writes_and_validates_final_processed_files`

**Me:** Did all tests pass?

**AI:** Yes. Full suite passed with `16 passed`.

---

## 7. Clarification Q&A captured during development

**Me:** What are `average_forever`, `average_2weeks`, `median_forever`, and
`median_2weeks`?

**AI:** SteamSpy playtime fields in minutes (lifetime and two-week average/median).
In the sampled raw payload, many values were zero, so derived playtime-hour
metrics are also zero for those records.

**Me:** Which code writes `usage_daily.csv`?

**AI:** `src/usage.py`, function `build_and_save(games)`, called from `etl.py`.

**Me:** Is `ai_transcript/transcript.md` automatically updated by pipeline runs?

**AI:** No. It changes only when edited manually.

---

## 8. Final state summary

**AI:** Final solution state:

- Raw layer: SteamSpy base + enrichment snapshots.
- Transform layer: normalized game model and genre summary.
- Analytical outputs: games, genre summary, daily usage, monthly metrics,
  quality report.
- Dashboard layer: multi-page analytics with filters, improved graphs, MAU/DAU
  KPIs, and AI-assisted narrative summary.
- Quality layer: expanded schema + key + consistency checks (18 checks total).
- Test layer: expanded to cover extract failures, usage model behavior,
  orchestration, and artifact validation (16 passing tests).

---

## 9. Ongoing dashboard quality-visibility updates

**Me:** Are we storing data-quality results somewhere? Can we see them in the
dashboard? Can we add an agentic layer that explains recurring errors?

**AI:** Implemented a persistent quality history mechanism and dashboard layer:

- Each ETL run now appends a quality snapshot to
  `data/processed/data_quality_history.jsonl`.
- Dashboard reads historical runs and computes top recurring failed checks over
  the last N runs.
- Data Quality page now includes an AI-style quality summary card based on run
  history.

**Me:** Add a proper section for showing data quality results in the dashboard.

**AI:** Reworked the Data Quality page into clear sections:

1. **Current run results** (KPIs, pass/fail distribution)
2. **Failing checks (current run)** table
3. **All checks** view in an expander
4. **Historical quality results** with lookback slider
5. **Trend charts** for failed checks and pass-rate over time
6. **Recurring failure table** and AI-style historical narrative summary

**Me:** Add color badges for each check row (pass/fail) to improve scanability.

**AI:** Added row-level status badges:

- `🟢 PASS`
- `🔴 FAIL`

These badges are now shown in the current-run checks tables.

**Me:** Did everything still pass after these updates?

**AI:** Yes. Re-ran the test suite and confirmed all tests pass (`17 passed`).

---

## 10. Flow documentation redesign (diagram-first)

**Me:** The documentation should show a proper end-to-end flow, not heavy text.
Include raw extraction to transformed layer, data-source details, and code
ownership clearly.

**AI:** Created a dedicated HTML documentation page at
`docs/etl_flow_documentation.html` using the same Steam-themed visual language
as the dashboard. Linked it at the top of README so reviewers can open it
first.

**Me:** Replace stage cards with an actual flow diagram.

**AI:** Rebuilt the page as a true flow diagram (SVG-based) with directional
arrows and embedded node details. The diagram now includes:

- Data source endpoints (`top100in2weeks`, `appdetails`)
- Stage-wise code ownership (`src/extract.py`, `src/transform.py`, `src/usage.py`,
  `src/growth.py`, `src/quality.py`, `etl.py`, `app.py`)
- Stage artifacts (`data/raw/...`, `data/processed/...`)
- Testing path overlay with command details

**Me:** Add how unit tests are run directly in the diagram.

**AI:** Added a dedicated testing branch in the flow with:

- Activate venv
- Run `pytest -q`
- Test files: `tests/test_etl.py`, `tests/test_pipeline_layers.py`
- Validation scope: transforms, quality rules, orchestration, artifacts

**Me:** Convert all node details to bullet points.

**AI:** Updated the diagram text so all detail lines are consistently
bullet-point formatted.

---

## 11. Dashboard readability and formatting refinements

**Me:** Improve readability in Title Usage and Market Snapshot, and remove
repeated data-source note lines.

**AI:** Implemented updates in `app.py`:

- Title Usage table values formatted for readability
- Top-5 metric charts show labeled values above bars
- Market Snapshot scatter enhanced with richer hover details and clearer axis
  interpretation notes
- Price Distribution redesigned into bucketed bars with percentage labels and
  supporting median/average price KPIs
- Removed persistent data-source footer/side notes from dashboard views

**Me:** Add comma formatting across the entire dashboard.

**AI:** Applied a broader comma-format pass:

- Global chart axis thousand separation enabled in shared figure styling
- KPI cards updated to use comma-separated values where applicable
- Key table/metric displays normalized for comma-readable counts
- Numeric narrative fields updated to align with comma-first readability

This preserved percentage and currency semantics while improving readability of
large numbers throughout dashboard pages.

---

## 12. Final readability tuning and transcript sync

**Me:** In Market Snapshot, remove x-axis labels from both charts:
Reception vs audience size and Price distribution.

**AI:** Updated dashboard rendering to hide x-axis tick labels in both
requested charts while retaining chart titles, hover details, and explanatory
notes for interpretation.

**Me:** In the Summary section, comma formatting looks clumsy. Use K/M style
instead.

**AI:** Updated Summary KPI cards to use compact readability format (K/M)
instead of comma-separated long values, including:

- Games tracked
- Live players (CCU)
- Total player-hours
- Markets
