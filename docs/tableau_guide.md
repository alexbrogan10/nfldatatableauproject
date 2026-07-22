# Tableau Build Guide

## 1. Connect the data

Open Tableau Desktop (or Tableau Public) → **Connect → Text File** → select
each CSV in `data/processed/`. Add all five as separate connections in one
data source (Tableau will let you relate/join them — see below) or keep them
as separate data sources per dashboard, whichever you prefer.

Alternatively, open `NFL_Dashboard_Starter.twb` (repo root) directly — it
pre-connects `games.csv`, `team_standings.csv`, `weekly_team_results.csv`,
`player_stats.csv`, and `teams.csv` with correct column types (integers,
booleans, dates) already set, so you skip the manual "browse & connect"
step and Tableau's occasionally-wrong CSV type auto-detection. It has no
worksheets/dashboards built in — those still get built in-app following the
sections below.

That file was generated (`scripts/build_tableau_workbook.py`) and validated
as well-formed XML with the right connection/column structure, but it
wasn't opened in an actual Tableau install to confirm Tableau accepts it
as-is — text-file connection XML isn't publicly documented. If it doesn't
open cleanly, fall back to connecting the five CSVs manually as described
above; nothing else in this repo depends on the `.twb` file.

| File | Grain | Rows |
|---|---|---|
| `games.csv` | one row per game | ~1,700 |
| `team_standings.csv` | one row per team per season | 192 |
| `weekly_team_results.csv` | one row per team per game, 2025 only | 570 |
| `player_stats.csv` | one row per player, 2025 season totals | ~2,175 |
| `teams.csv` | one row per team | 32 |
| `player_stats_data_dictionary.csv` | one row per stat column | 100 |

## 2. Join / relate keys

- `team_standings.team` ↔ `weekly_team_results.team` ↔ `player_stats.team` ↔ `teams.team` —
  all use the same team abbreviation, normalized so they match exactly (the
  ETL rewrites ESPN's `LAR`/`WSH` to nflverse's `LA`/`WAS` for this reason —
  don't skip that step if you re-pull player stats another way). Use Tableau's
  **Relationships** (not a hard join) if combining standings with player
  stats, since they're at different grains (team-season vs. player-season).
- `teams.team` is a clean lookup table (full name, conference, division) —
  relate it to any of the other four on `team` to get a nicer display name
  than the raw abbreviation, without duplicating rows.
- `games.game_id` = `weekly_team_results.game_id` if you want to bring in venue/weather
  fields from `games.csv` into the per-team view.
- `player_stats` has no direct key into `games`/`standings` other than `team` + `season` —
  it's season totals, not game-by-game, so don't try to join it at the game grain.
- `player_stats_data_dictionary.column` matches the column *names* in
  `player_stats.csv` (not a join key on the data itself) — use it as a
  reference while building calculated fields, not as a relate target.

Simplest approach: build most sheets from a single CSV, and only relate
across files where you specifically need cross-cutting fields (e.g. "top
fantasy scorer per division" would relate `player_stats` to `team_standings`
on `team`).

## 3. Key fields per file

**`games.csv`** — `season`, `week`, `game_type` (REG/WC/DIV/CONF/SB), `away_team`,
`home_team`, `away_score`, `home_score`, `result` (home margin), `completed`
(boolean — filter to `True` for played games, `False` to show the upcoming
schedule), `roof`/`surface`/`stadium` for venue analysis.

**`team_standings.csv`** — `season`, `conf`, `division`, `team`, `wins`/`losses`/`ties`,
`pct`, `div_rank`, `scored`/`allowed`/`net` (points), `sos`/`sov` (strength of
schedule/victory), `seed` (playoff seed, blank if missed playoffs), `playoff`
(how far they went, e.g. `LostDV`, `WonSB`).

**`weekly_team_results.csv`** — `week`, `team`, `opponent`, `team_score`/`opp_score`,
`win`/`loss`/`tie` (booleans), `point_diff`, `cum_wins`/`cum_losses`/`cum_point_diff`
(running totals through the season — use these directly for a win-progression
line chart, no table calc needed).

**`player_stats.csv`** — `name`, `team`, `position`, then stat columns prefixed by
category: `passing_*`, `rushing_*`, `receiving_*`, `defensive_*`,
`defensiveinterceptions_*`, `scoring_*`, `returning_*`, `kicking_*`, `punting_*`.
Fantasy totals: `fantasy_points_standard`, `fantasy_points_half_ppr`,
`fantasy_points_ppr`.

Fantasy scoring formula used (standard categories, no distance-based FG
bonus): passing yards ÷ 25 + passing TD × 4 − INT × 2, rushing yards ÷ 10 +
rushing TD × 6, receiving yards ÷ 10 + receiving TD × 6 (+ receptions × 1 for
PPR / × 0.5 for half-PPR), fumbles lost × −2, return TD × 6, FG made × 3, XP
made × 1.

Note: `team` and `position` are blank for ~300 players who logged games in
2025 but are no longer on an active 32-team roster (cut, retired, practice
squad only) — ESPN's roster endpoint only reflects current rosters.

Full descriptions for every `player_stats.csv` column (what it measures,
which category it belongs to) are in `player_stats_data_dictionary.csv` —
open it alongside Tableau's field list when you're not sure what an
abbreviation like `receiving_receivingYardsAfterCatch` means.

## 4. Ready-to-paste calculated fields

Right-click in the Data pane → **Create Calculated Field**, paste the
formula, name it as shown.

**`Position Group`** — collapse ESPN's granular positions (DE/DT/OLB/etc.)
into the buckets fantasy football actually uses:
```
IF [position] = "QB" THEN "QB"
ELSEIF [position] = "RB" THEN "RB"
ELSEIF [position] = "WR" THEN "WR"
ELSEIF [position] = "TE" THEN "TE"
ELSEIF [position] = "PK" THEN "K"
ELSEIF [position] IN ("DE","DT","NT","OLB","ILB","MLB","LB","CB","S","SS","FS","DB") THEN "DEF/IDP"
ELSE "Other"
END
```

**`Selected Fantasy Format`** — a parameter-driven switch so one chart can
toggle between scoring formats instead of building three. First create a
string **Parameter** named `Scoring Format` with a list of values `Standard`,
`Half PPR`, `PPR` (default `PPR`), then add this calculated field:
```
CASE [Scoring Format]
WHEN "Standard" THEN [fantasy_points_standard]
WHEN "Half PPR" THEN [fantasy_points_half_ppr]
WHEN "PPR" THEN [fantasy_points_ppr]
END
```
Show the parameter control on your fantasy dashboard so viewers can flip it live.

**`Fantasy Points Per Game`**:
```
[fantasy_points_ppr] / [general_gamesPlayed]
```

**`Win %`** (if you want it as a calc instead of using `team_standings.pct` directly):
```
[wins] / ([wins] + [losses] + [ties])
```

**`Point Differential`** (team_standings):
```
[scored] - [allowed]
```

**`Home Win`** (games.csv, for home/away win-rate charts):
```
IF [completed] THEN [home_score] > [away_score] END
```

**`Made Playoffs`** (team_standings — `seed` is null for teams that missed):
```
NOT ISNULL([seed])
```

## 5. Suggested dashboards

**Team Performance** (source: `team_standings.csv` + `weekly_team_results.csv`)
- Division standings table: `division` → `team`, sorted by `wins`, colored by `pct`
- Win/loss trend: line chart of `cum_wins` by `week`, one line per `team`, filter to a division/conference
- Points for vs. points against: scatter plot, `scored` (x) vs `allowed` (y), sized by `wins`, one dot per team
- Season-over-season trend: `wins` by `season`, one line per team (needs `team_standings.csv` across all years)

**Game Results** (source: `games.csv`)
- Schedule/results table filtered to `completed = False` for "what's coming up"
- Score margin distribution: histogram of `result`
- Home vs. away win rate: bar chart split by `location`
- Games by `roof`/`surface` type

**Player Stats** (source: `player_stats.csv`)
- Passing leaderboard: bar chart of `passing_passingYards`, filtered `position = QB`
- Rushing/receiving leaders: same pattern with `rushing_rushingYards` / `receiving_receivingYards`
- Efficiency scatter: `passing_passingAttempts` (x) vs `passing_QBRating` (y), sized by `passing_passingTouchdowns`
- Defensive leaders: `defensive_totalTackles` + `defensive_sacks` combo chart

**Fantasy Football** (source: `player_stats.csv`)
- Top overall: bar chart of `fantasy_points_ppr`, top 25, colored by `position`
- Positional rankings: same chart filtered per `position` with a parameter to switch position
- Standard vs. PPR comparison: dual-axis or scatter of `fantasy_points_standard` vs `fantasy_points_ppr` to spot volume-catch players
- Value finder: `fantasy_points_ppr` per game (`fantasy_points_ppr / general_gamesPlayed`) vs total, to separate high-floor from boom/bust players

## 6. Filters/parameters worth adding

- `season` filter (works on `games.csv`/`team_standings.csv`, since they span 2021–2026)
- `position` parameter for the player stats dashboards
- `game_type` filter (REG/WC/DIV/CONF/SB) to separate regular season from playoffs
- A PPR-format parameter (Standard / Half / Full) driving a calculated field that picks the right `fantasy_points_*` column
