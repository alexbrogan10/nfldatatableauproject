"""
Pulls player season statistics from ESPN's public stats API for a given
season, enriches each player with team/position from ESPN roster endpoints,
computes fantasy points, and writes a Tableau-ready CSV to data/processed/.

Sources (public, unauthenticated):
- https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/statistics/byathlete
- https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/roster
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "processed"

SEASON = 2025
SEASON_TYPE = 2  # regular season
PAGE_LIMIT = 100  # ESPN's pagination breaks past page 1 when limit=200
STATS_URL = (
    "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/"
    "statistics/byathlete"
)
ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/roster"

TEAM_ABBRS = [
    "ari", "atl", "bal", "buf", "car", "chi", "cin", "cle", "dal", "den",
    "det", "gb", "hou", "ind", "jax", "kc", "lac", "lar", "lv", "mia",
    "min", "ne", "no", "nyg", "nyj", "phi", "pit", "sea", "sf", "tb",
    "ten", "wsh",
]

SESSION = requests.Session()


def fetch_player_stat_pages() -> list[dict]:
    """Paginate through the whole league sorted by games played, collecting
    every athlete's full stat line (all categories come back regardless of
    sort field). Stat field names live in the response's top-level
    `categories` schema (keyed by category name), not on each athlete."""
    # NOTE: this ESPN endpoint's `page`+`limit` pagination has an undocumented
    # quirk where specific (page, limit) combinations silently return zero
    # athletes even though more data exists (reproducible, not rate-limiting;
    # an `offset` param exists but is silently ignored by the server). We
    # work around it by shrinking the page size when a window comes back
    # empty, and skipping forward a little if even limit=1 fails, rather
    # than trying to fully explain the server-side bug.
    athletes: dict[str, dict] = {}
    category_names: dict[str, list[str]] = {}
    start = 0
    limit = PAGE_LIMIT
    consecutive_skips = 0
    while start < 3000 and consecutive_skips < 6:
        if start % limit != 0:
            limit = 1
        page = start // limit + 1
        params = {
            "region": "us",
            "lang": "en",
            "contentorigin": "espn",
            "isqualified": "false",
            "page": page,
            "limit": limit,
            "season": SEASON,
            "seasontype": SEASON_TYPE,
            "sort": "general.gamesPlayed:desc",
        }
        resp = SESSION.get(STATS_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        page_athletes = data.get("athletes", [])

        if not page_athletes:
            if limit > 1:
                limit = max(1, limit // 2)
            else:
                start += 10
                limit = PAGE_LIMIT
                consecutive_skips += 1
            time.sleep(0.2)
            continue

        for cat_schema in data.get("categories", []):
            category_names.setdefault(cat_schema["name"], cat_schema["names"])

        for a in page_athletes:
            athlete_id = a["athlete"]["id"]
            row = {
                "athlete_id": athlete_id,
                "name": a["athlete"].get("displayName"),
            }
            for cat in a.get("categories", []):
                names = category_names.get(cat["name"], [])
                for name, value in zip(names, cat["values"]):
                    row[f"{cat['name']}_{name}"] = value
            athletes[athlete_id] = row

        # Athletes are sorted by games played descending, so once a window is
        # entirely players with 0 games we've covered everyone active.
        last_row = athletes[page_athletes[-1]["athlete"]["id"]]
        if last_row.get("general_gamesPlayed", 0) in (0, None):
            break

        start += len(page_athletes)
        limit = PAGE_LIMIT
        consecutive_skips = 0
        time.sleep(0.2)

    return list(athletes.values())


def fetch_team_rosters() -> pd.DataFrame:
    """Map athlete_id -> team/position by walking each team's roster."""
    rows = []
    for team in TEAM_ABBRS:
        resp = SESSION.get(ROSTER_URL.format(team=team), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        team_abbr = data.get("team", {}).get("abbreviation", team.upper())
        for group in data.get("athletes", []):
            for item in group.get("items", []):
                rows.append({
                    "athlete_id": item["id"],
                    "team": team_abbr,
                    "position": (item.get("position") or {}).get("abbreviation"),
                })
        time.sleep(0.2)
    return pd.DataFrame(rows)


def compute_fantasy_points(df: pd.DataFrame) -> pd.DataFrame:
    """Standard fantasy scoring approximation (no distance-based FG bonus)."""

    def col(name: str) -> pd.Series:
        return df[name].fillna(0) if name in df.columns else 0

    passing_pts = col("passing_passingYards") / 25 + col("passing_passingTouchdowns") * 4 \
        + col("passing_interceptions") * -2
    rushing_pts = col("rushing_rushingYards") / 10 + col("rushing_rushingTouchdowns") * 6
    receiving_base = col("receiving_receivingYards") / 10 + col("receiving_receivingTouchdowns") * 6
    fumble_pts = (col("rushing_rushingFumblesLost") + col("receiving_receivingFumblesLost")) * -2
    return_pts = col("scoring_returnTouchdowns") * 6
    kicking_pts = col("kicking_fieldGoalsMade") * 3 + col("kicking_extraPointsMade") * 1

    base = passing_pts + rushing_pts + receiving_base + fumble_pts + return_pts + kicking_pts
    df["fantasy_points_standard"] = base
    df["fantasy_points_half_ppr"] = base + col("receiving_receptions") * 0.5
    df["fantasy_points_ppr"] = base + col("receiving_receptions") * 1.0
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {SEASON} player stat leaderboard from ESPN ...")
    stat_rows = fetch_player_stat_pages()
    stats_df = pd.DataFrame(stat_rows)
    print(f"  pulled stats for {len(stats_df)} athletes")

    print("Fetching team rosters for position/team enrichment ...")
    rosters_df = fetch_team_rosters()
    print(f"  pulled {len(rosters_df)} roster entries across {len(TEAM_ABBRS)} teams")

    merged = stats_df.merge(rosters_df, on="athlete_id", how="left")
    merged = merged[merged.get("general_gamesPlayed", 0).fillna(0) > 0].copy()
    merged["season"] = SEASON
    merged = compute_fantasy_points(merged)

    merged = merged.sort_values("fantasy_points_ppr", ascending=False)
    merged.to_csv(OUT_DIR / "player_stats.csv", index=False)
    print(f"  wrote {len(merged)} rows -> data/processed/player_stats.csv")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Network error while fetching source data: {exc}", file=sys.stderr)
        sys.exit(1)
