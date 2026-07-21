"""
Pulls game/schedule and standings data from the public nflverse/nfldata
repository and writes Tableau-ready CSVs to data/processed/.

Source: https://github.com/nflverse/nfldata (data/games.csv, data/standings.csv)
"""
import io
import sys
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "processed"

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
STANDINGS_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/standings.csv"

# Years of history to keep for trend charts. The most recently completed
# season is treated as the "current" season for standings/leaderboards.
SEASON_START = 2021
CURRENT_SEASON = 2025


def fetch_csv(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.text))


def build_games() -> pd.DataFrame:
    df = fetch_csv(GAMES_URL)
    df = df[df["season"] >= SEASON_START].copy()
    df["completed"] = df["home_score"].notna() & df["away_score"].notna()
    keep_cols = [
        "game_id", "season", "game_type", "week", "gameday", "weekday", "gametime",
        "away_team", "away_score", "home_team", "home_score", "location", "result",
        "total", "overtime", "div_game", "roof", "surface", "stadium", "completed",
    ]
    df = df[[c for c in keep_cols if c in df.columns]]
    return df.sort_values(["season", "week", "gameday"])


def build_standings() -> pd.DataFrame:
    df = fetch_csv(STANDINGS_URL)
    df = df[df["season"] >= SEASON_START].copy()
    return df.sort_values(["season", "conf", "division", "wins"], ascending=[True, True, True, False])


def build_weekly_team_results(games: pd.DataFrame, season: int) -> pd.DataFrame:
    """Unpivot home/away games into one row per team per game for trend charts."""
    season_games = games[(games["season"] == season) & (games["completed"])].copy()

    home = season_games.rename(columns={
        "home_team": "team", "away_team": "opponent",
        "home_score": "team_score", "away_score": "opp_score",
    })
    home["is_home"] = True

    away = season_games.rename(columns={
        "away_team": "team", "home_team": "opponent",
        "away_score": "team_score", "home_score": "opp_score",
    })
    away["is_home"] = False

    cols = ["game_id", "season", "game_type", "week", "gameday", "team", "opponent",
            "team_score", "opp_score", "is_home"]
    combined = pd.concat([home[cols], away[cols]], ignore_index=True)
    combined["win"] = combined["team_score"] > combined["opp_score"]
    combined["loss"] = combined["team_score"] < combined["opp_score"]
    combined["tie"] = combined["team_score"] == combined["opp_score"]
    combined["point_diff"] = combined["team_score"] - combined["opp_score"]

    combined = combined.sort_values(["team", "week"])
    combined["cum_wins"] = combined.groupby("team")["win"].cumsum()
    combined["cum_losses"] = combined.groupby("team")["loss"].cumsum()
    combined["cum_point_diff"] = combined.groupby("team")["point_diff"].cumsum()
    return combined.sort_values(["team", "week"])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching games.csv ...")
    games = build_games()
    games.to_csv(OUT_DIR / "games.csv", index=False)
    print(f"  wrote {len(games)} rows -> data/processed/games.csv")

    print("Fetching standings.csv ...")
    standings = build_standings()
    standings.to_csv(OUT_DIR / "team_standings.csv", index=False)
    print(f"  wrote {len(standings)} rows -> data/processed/team_standings.csv")

    print(f"Building weekly team results for {CURRENT_SEASON} ...")
    weekly = build_weekly_team_results(games, CURRENT_SEASON)
    weekly.to_csv(OUT_DIR / "weekly_team_results.csv", index=False)
    print(f"  wrote {len(weekly)} rows -> data/processed/weekly_team_results.csv")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Network error while fetching source data: {exc}", file=sys.stderr)
        sys.exit(1)
