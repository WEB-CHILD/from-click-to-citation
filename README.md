# Navigation-history overview tools

Small Python 3 scripts for inspecting the JSON files in
[navigation_histories/](navigation_histories/). Run them from the project root.

`file_summary.py` and `overview.py` use only the standard library.
`render_table.py` needs **matplotlib** — see [Setup](#setup-for-render_tablepy).

The outputs are anonymised: each filename is mapped to a stable participant id
(`P01`, `P02`, …) stored in [participant_map.json](participant_map.json). The
same file always keeps the same id; new files get the next free number.

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
  (journal-style horizontal rules, bold header, centred numbers). Writes vector
  **PDF** and **SVG** (best for LaTeX/Word — scale without pixelation) plus a
  300-DPI **PNG**, into the [output/](output/) folder.

  ```bash
  python3 render_table.py                          # -> output/table.{pdf,png,svg}
  python3 render_table.py navigation_histories     # explicit input folder
  python3 render_table.py --out figures/summary    # custom basename/folder
  python3 render_table.py --formats pdf png         # choose output formats
  python3 render_table.py --dpi 600                 # raster resolution for PNG
  ```

  In LaTeX include the vector file, e.g. `\includegraphics{output/table.pdf}`.
  Column titles can be adjusted via the `PRETTY` dict near the top of the
  script.

- **`grouped_table.py`** — splits participants into two browsing styles and
  tabulates each group with a per-group mean row. **Query-based** participants
  have more queries than playback-link clicks; **click-based** participants have
  more playback clicks than queries (any exact ties are listed as *balanced*).
  Prints as text and, unless `--no-image`, renders a publication image to
  [output/](output/) (`grouped_table.{pdf,png,svg}`). Needs matplotlib for the
  image — see [Setup](#setup-for-render_tablepy).

  ```bash
  python3 grouped_table.py                       # text + output/grouped_table.*
  python3 grouped_table.py path/to/folder        # a different folder
  python3 grouped_table.py --no-image            # text only, no matplotlib needed
  python3 grouped_table.py --out figures/groups  # custom image basename/folder
  ```

- **`query_click_timeline.py`** — for each participant in the query-based group,
  a chronological panel of their `query`, `search result clicked` and `playback
  link clicked` events (entry number on the x-axis, the three action types on
  three y-levels, connected by a line and coloured by type) so you can read the
  back-and-forth between searching, clicking results, and following playback
  links. Renders to [output/](output/) (`query_click_timeline.{pdf,png,svg}`);
  needs matplotlib.

  ```bash
  python3 query_click_timeline.py                  # -> output/query_click_timeline.*
  python3 query_click_timeline.py --ncols 3        # panel columns (default 2)
  python3 query_click_timeline.py --out figures/timeline
  ```

- **`click_timeline.py`** — the click-based counterpart of the above: the same
  chronological panels for every participant with more playback clicks than
  queries. Reuses the plotting code. Renders to [output/](output/)
  (`click_timeline.{pdf,png,svg}`); needs matplotlib.

  ```bash
  python3 click_timeline.py                        # -> output/click_timeline.*
  python3 click_timeline.py --ncols 3
  ```

- **`overview.py`** — a deeper per-file report: action breakdown, archived date
  range, and the most common queries and domains.

  ```bash
  python3 overview.py navigation_histories/markus_nissen.json
  python3 overview.py navigation_histories/            # every file + a TOTAL
  python3 overview.py navigation_histories/ --top 20   # show more top queries/domains
  ```

## Setup (for `render_table.py`)

`render_table.py` needs matplotlib. This project uses a dedicated pyenv
virtualenv, pinned in [.python-version](.python-version), so it activates
automatically when you `cd` into the folder. To recreate it from scratch:

```bash
pyenv virtualenv 3.13.7 from-click-to-citation
pyenv local from-click-to-citation
pip install matplotlib
```
