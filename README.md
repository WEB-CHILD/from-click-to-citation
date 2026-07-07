# Navigation-history overview tools

Small Python 3 scripts for inspecting the JSON files in
[navigation_histories/](navigation_histories/). Run them from the project root.

`file_summary.py`, `overview.py` and `history_markdown.py` use only the standard
library. The image-producing scripts (`render_table.py`, `grouped_table.py`,
`query_click_timeline.py`, `click_timeline.py`, `repeat_runs.py`) need
**matplotlib** — see [Setup](#setup-matplotlib).

The outputs are anonymised: each filename is mapped to a stable participant id
(`P01`, `P02`, …) stored in [participant_map.json](participant_map.json). The
same file always keeps the same id; new files get the next free number.

Generated files land in [output/](output/): the two summary tables write
`table.png` and `grouped_table.png` directly, while the per-participant scripts
each write into their own sub-folder (`query_click_timeline/`, `click_timeline/`,
`repeat_runs/`, `markdown/`). Image scripts default to **PNG**; pass `--formats`
for vector PDF/SVG. `output/markdown/` and `output/repeat_runs/` are gitignored.

## The scripts

- **`file_summary.py`** — a one-line-per-participant table: how many entries
  each file has, the breakdown by action type (`query`, `search result
  clicked`, `playback link clicked`), and two derived ratios (`query/click` and
  `playback/click`, i.e. per search-result-click). Ends with `TOTAL`,
  `AVERAGE`, `MEDIAN`, `MAX` and `MIN` rows across all participants.

  ```bash
  python3 file_summary.py                 # whole navigation_histories/ folder
  python3 file_summary.py path/to/folder  # a different folder
  ```

- **`render_table.py`** — renders the same table as a publication-quality image
  (journal-style horizontal rules, bold header, centred numbers). Writes a
  300-DPI **PNG** into the [output/](output/) folder.

  ```bash
  python3 render_table.py                          # -> output/table.png
  python3 render_table.py navigation_histories     # explicit input folder
  python3 render_table.py --out figures/summary    # custom basename/folder
  python3 render_table.py --formats pdf png svg     # add vector formats
  python3 render_table.py --dpi 600                 # raster resolution for PNG
  ```

  For LaTeX/Word add `--formats pdf` and include the vector file, e.g.
  `\includegraphics{output/table.pdf}`. Column titles can be adjusted via the
  `PRETTY` dict near the top of the script.

- **`grouped_table.py`** — splits participants into two browsing styles and
  tabulates each group with a per-group mean row. **Query-based** participants
  have more queries than playback-link clicks; **click-based** participants have
  more playback clicks than queries (any exact ties are listed as *balanced*).
  Prints as text and, unless `--no-image`, renders an image to
  [output/](output/) (`grouped_table.png`). Needs matplotlib for the image —
  see [Setup](#setup-matplotlib).

  ```bash
  python3 grouped_table.py                       # text + output/grouped_table.png
  python3 grouped_table.py path/to/folder        # a different folder
  python3 grouped_table.py --no-image            # text only, no matplotlib needed
  python3 grouped_table.py --out figures/groups  # custom image basename/folder
  ```

- **`query_click_timeline.py`** — for each participant in the query-based group,
  a chronological panel of their `query`, `search result clicked` and `playback
  link clicked` events (entry number on the x-axis, the three action types on
  three y-levels, connected by a line and coloured by type) so you can read the
  back-and-forth between searching, clicking results, and following playback
  links. Writes **one image per participant** into
  `output/query_click_timeline/` (`P01.png`, `P03.png`, …); needs matplotlib.

  ```bash
  python3 query_click_timeline.py                  # -> output/query_click_timeline/*.png
  python3 query_click_timeline.py path/to/folder
  python3 query_click_timeline.py --out-dir figures/timeline
  ```

- **`click_timeline.py`** — the click-based counterpart of the above: the same
  per-participant panels for every participant with more playback clicks than
  queries. Reuses the plotting code. Writes one image per participant into
  `output/click_timeline/`; needs matplotlib.

  ```bash
  python3 click_timeline.py                        # -> output/click_timeline/*.png
  python3 click_timeline.py --out-dir figures/clicks
  ```

- **`repeat_runs.py`** — finds where the **exact same action repeats
  back-to-back** in a participant's history (same playback link clicked again
  and again, or the same query fired several times in a row). "Identical" means
  same action *and* same target — for a click, both the url *and* the harvest
  (capture) date must match; for a query, the query string plus its filters.
  Renders one booktabs-style table image per participant listing
  their runs (longest first), plus a `summary` table ranking everyone's longest
  streak, into `output/repeat_runs/`; needs matplotlib.

  ```bash
  python3 repeat_runs.py                    # runs of length >= 2
  python3 repeat_runs.py --min-run 3        # only tables for runs of 3+
  python3 repeat_runs.py --out-dir figures/repeats
  ```

- **`history_markdown.py`** — renders each participant's navigation history as a
  Markdown document: a chronological table of every entry with its details (the
  query string and any filters, or the clicked url plus its archived copy and
  capture date). Writes one `P01.md`, `P02.md`, … into `output/markdown/`.
  Standard library only.

  ```bash
  python3 history_markdown.py               # all files -> output/markdown/*.md
  python3 history_markdown.py --only P01 P05 # just these participants
  python3 history_markdown.py --out-dir figures/md
  ```

- **`overview.py`** — a deeper per-file report: action breakdown, archived date
  range, and the most common queries and domains.

  ```bash
  python3 overview.py navigation_histories/markus_nissen.json
  python3 overview.py navigation_histories/            # every file + a TOTAL
  python3 overview.py navigation_histories/ --top 20   # show more top queries/domains
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
