# Navigation-history overview tools

Small Python 3 scripts for inspecting the anonymised navigation histories. Run
them from the project root.

This repository holds the code and the generated tables and figures in
[output/](output/), but not the data. To rerun the scripts, put the anonymised
dataset (`P01.json` … `P16.json`) in a folder called `anonymised/` in the project
root, or pass another folder as an argument.

The histories are in the SolrWayback export format of pull request 11: actions
such as `QUERY`, `SEARCH_RESULT_CLICKED`, `PLAYBACK_LINK_CLICKED` and
`PLAYBACK_FAILED`, and a `timestamp`, `from` and `tab` on each entry. The format
is described in the README that comes with the dataset. They are made in two
steps from private data that is not in the repository:

1. `correct_histories.py`, which is also kept out of the repository, matches the
   raw workshop histories (`navigation_histories/`) to the server logs (`logs/`)
   and writes corrected copies to `navigation_histories_corrected/`.
2. `anonymise_histories.py` pseudonymises those into `anonymised/`, using the
   gitignored `anonymisation_key.json`.

`file_summary.py`, `overview.py` and `history_markdown.py` use only the standard
library. The image-producing scripts (`render_table.py`, `grouped_table.py`,
`query_click_timeline.py`, `click_timeline.py`, `repeat_runs.py`) need
**matplotlib** — see [Setup](#setup-matplotlib).

The files in `anonymised/` are already named by participant id (`P01.json`, …),
and the scripts keep those ids. Any other folder passed to a script is mapped to
ids through `participant_map.json` instead.

Generated files land in [output/](output/): the two summary tables write
`table.png` and `grouped_table.png` directly, while the per-participant scripts
each write into their own sub-folder (`query_click_timeline/`, `click_timeline/`,
`repeat_runs/`, `markdown/`). Image scripts default to **PNG**; pass `--formats`
for vector PDF/SVG. `output/markdown/` and `output/repeat_runs/` are gitignored.

## The scripts

- **`file_summary.py`** — a one-line-per-participant table: how many entries
  each file has, the breakdown by all nine action types, and two derived ratios
  (`query/click` and `link/click`, i.e. queries and link clicks per search
  result click). Ends with `TOTAL`,
  `AVERAGE`, `MEDIAN`, `MAX` and `MIN` rows across all participants.

  ```bash
  python3 file_summary.py                 # whole anonymised/ folder
  python3 file_summary.py path/to/folder  # a different folder
  ```

- **`render_table.py`** — renders the same table as a publication-quality image
  (journal-style horizontal rules, bold header, centred numbers). Writes a
  300-DPI **PNG** into the [output/](output/) folder.

  ```bash
  python3 render_table.py                          # -> output/table.png
  python3 render_table.py anonymised               # explicit input folder
  python3 render_table.py --out figures/summary    # custom basename/folder
  python3 render_table.py --formats pdf png svg     # add vector formats
  python3 render_table.py --dpi 600                 # raster resolution for PNG
  ```

  For LaTeX/Word add `--formats pdf` and include the vector file, e.g.
  `\includegraphics{output/table.pdf}`. Column titles can be adjusted via the
  `PRETTY` dict near the top of the script.

- **`grouped_table.py`** — splits participants into two browsing styles and
  tabulates each group with a per-group mean row. **Query-based** participants
  have more queries than link clicks (`PLAYBACK_LINK_CLICKED`); **click-based**
  participants have more link clicks than queries (any exact ties are listed as
  *balanced*). Failed playbacks get their own column.
  Prints as text and, unless `--no-image`, renders an image to
  [output/](output/) (`grouped_table.png`). Needs matplotlib for the image —
  see [Setup](#setup-matplotlib).

  ```bash
  python3 grouped_table.py                       # text + output/grouped_table.png
  python3 grouped_table.py path/to/folder        # a different folder
  python3 grouped_table.py --no-image            # text only, no matplotlib needed
  python3 grouped_table.py --out figures/groups  # custom image basename/folder
  ```

- **`grouped_table_cleaned.py`** — the same grouped table, but any run of the
  *exact same action* repeated more than `--max-run` times in a row (default 10)
  is dropped before counting, then participants are re-classified from the
  cleaned numbers. This strips out long stretches of one identical event — e.g.
  one page reloading itself hundreds of times — that would otherwise swamp
  the totals. "Exact same action" matches `repeat_runs.py` (same url *and*
  harvest date for a click, or query string plus filters for a query). Prints
  the text table and what was removed, and renders `grouped_table_cleaned.png`
  to [output/](output/); needs matplotlib.

  ```bash
  python3 grouped_table_cleaned.py               # text + output/grouped_table_cleaned.png
  python3 grouped_table_cleaned.py --max-run 5   # stricter: drop runs longer than 5
  python3 grouped_table_cleaned.py --no-image    # text only
  ```

- **`query_click_timeline.py`** — for each participant in the query-based group,
  a chronological panel of every entry (entry number on the x-axis; queries,
  result clicks, link clicks, failed playbacks and other navigation on five
  y-levels, connected by a line and coloured by level) so you can read the
  back-and-forth between searching, clicking results, and following links. Writes **one image per participant** into
  `output/query_click_timeline/` (`P01.png`, `P03.png`, …); needs matplotlib.

  ```bash
  python3 query_click_timeline.py                  # -> output/query_click_timeline/*.png
  python3 query_click_timeline.py path/to/folder
  python3 query_click_timeline.py --out-dir figures/timeline
  ```

- **`click_timeline.py`** — the click-based counterpart of the above: the same
  per-participant panels for every participant with more link clicks than
  queries. Reuses the plotting code. Writes one image per participant into
  `output/click_timeline/`; needs matplotlib.

  ```bash
  python3 click_timeline.py                        # -> output/click_timeline/*.png
  python3 click_timeline.py --out-dir figures/clicks
  ```

- **`repeat_runs.py`** — finds where the **exact same action repeats
  back-to-back** in a participant's history (the same page reloading itself
  again and again, or the same query fired several times in a row). "Identical"
  means same action *and* same target — for a page action, both the url *and*
  the harvest (capture) date must match; for a query, the query string plus its filters.
  Renders one booktabs-style table image per participant listing
  their runs (longest first), plus a `summary` table ranking everyone's longest
  streak, into `output/repeat_runs/`; needs matplotlib.

  ```bash
  python3 repeat_runs.py                    # runs of length >= 2
  python3 repeat_runs.py --min-run 3        # only tables for runs of 3+
  python3 repeat_runs.py --out-dir figures/repeats
  ```

- **`time_travel.py`** — how far participants move through *capture time*
  while browsing. Each search result tab is a chain; each `PLAYBACK_LINK_CLICKED`
  in it is a step, measured from the capture date of the page the link was on
  (its `from` entry). Toolbar clicks and failed playbacks are counted
  separately. Prints a per-participant summary, with `--detail` every chain step
  by step, and with `--png` the summary as an image. Archived URLs appear as
  per-participant `site N · page M` labels.

  ```bash
  python3 time_travel.py --detail --out-file output/time_travel.txt --png
  python3 time_travel.py --detail --markdown --out-file output/time_travel.md
  python3 time_travel.py --detail --only P08   # one participant
  ```

- **`history_markdown.py`** — renders each participant's navigation history as a
  Markdown document: a chronological table of every entry with its time of day,
  action, tab and `from` entry, and its details (the query string and any
  filters, or the url plus its archived copy and capture date). Writes one `P01.md`, `P02.md`, … into `output/markdown/`.
  Standard library only.

  ```bash
  python3 history_markdown.py               # all files -> output/markdown/*.md
  python3 history_markdown.py --only P01 P05 # just these participants
  python3 history_markdown.py --out-dir figures/md
  ```

- **`overview.py`** — a deeper per-file report: action breakdown, archived date
  range, and the most common queries and domains.

  ```bash
  python3 overview.py                          # every file in anonymised/ + a TOTAL
  python3 overview.py anonymised/P08.json
  python3 overview.py anonymised/ --top 20     # show more top queries/domains
  ```

## Setup (matplotlib)

The image-producing scripts need matplotlib. This project uses a dedicated pyenv
virtualenv, pinned in [.python-version](.python-version), so it activates
automatically when you `cd` into the folder. To recreate it from scratch:

```bash
pyenv virtualenv 3.13.7 from-click-to-citation
pyenv local from-click-to-citation
pip install matplotlib
```
