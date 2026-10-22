"""Build NFL_Analysis.xlsx: every processed CSV as an Excel Table, plus
ready-made PivotTables and slicers.

Step 1 (pandas + openpyxl, runs anywhere) writes the data sheets as Excel
Tables with a few lookup/helper columns already filled in, so PivotTables
can group by full team name, conference, division, and position group
without any joins.

Step 2 (Excel via COM, Windows + Excel only) opens that file and adds the
PivotTable sheets. Skip it with --no-pivots to get just the tables.

Usage:
    python scripts/build_excel_workbook.py
    python scripts/build_excel_workbook.py --no-pivots
    python scripts/build_excel_workbook.py --free-agency-db ../nfl_free_agency.db
"""

import argparse
import sqlite3
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "NFL_Analysis.xlsx"
FREE_AGENCY_CSV = PROCESSED / "offseason_moves_2026.csv"

FONT = "Arial"

# Same buckets as the "Position Group" calculated field in docs/tableau_guide.md
POSITION_GROUPS = {
    "QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "PK": "K",
    **{p: "DEF/IDP" for p in
       ("DE", "DT", "NT", "OLB", "ILB", "MLB", "LB", "CB", "S", "SS", "FS", "DB")},
}

# The free agency data uses roster-style positions (EDGE, OT, OG...), so it
# gets its own offense/defense line groupings instead of the fantasy buckets
FA_POSITION_GROUPS = {
    "QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
    **{p: "OL" for p in ("OT", "OG", "C", "OL")},
    **{p: "DL" for p in ("EDGE", "DL", "DT", "DE")},
    "LB": "LB",
    **{p: "DB" for p in ("CB", "S", "DB")},
    **{p: "ST" for p in ("K", "P", "LS")},
}

PLAYER_COLUMNS = {
    "name": "Player", "team": "Team", "position": "Position",
    "general_gamesPlayed": "Games",
    "passing_passingYards": "Pass Yds", "passing_passingTouchdowns": "Pass TD",
    "passing_interceptions": "INT",
    "rushing_rushingAttempts": "Rush Att", "rushing_rushingYards": "Rush Yds",
    "rushing_rushingTouchdowns": "Rush TD",
    "receiving_receivingTargets": "Targets", "receiving_receptions": "Rec",
    "receiving_receivingYards": "Rec Yds", "receiving_receivingTouchdowns": "Rec TD",
    "defensive_totalTackles": "Tackles", "defensive_sacks": "Sacks",
    "defensiveinterceptions_interceptions": "Def INT",
    "kicking_fieldGoalsMade": "FG Made", "kicking_fieldGoalAttempts": "FG Att",
    "fantasy_points_standard": "Fantasy Std",
    "fantasy_points_half_ppr": "Fantasy Half PPR",
    "fantasy_points_ppr": "Fantasy PPR",
}


def money_to_number(series):
    cleaned = series.fillna("").astype(str).str.replace(r"[$,\s]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def load_free_agency(db_path):
    """Export the offseason_moves table to a CSV in data/processed, so the
    workbook build doesn't depend on a database outside the repo."""
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql("SELECT * FROM offseason_moves", conn)
    df = df[df["Player"].fillna("").str.strip() != ""]  # drop blank separator rows
    df.to_csv(FREE_AGENCY_CSV, index=False)
    print(f"Exported {len(df)} offseason moves -> {FREE_AGENCY_CSV.relative_to(ROOT)}")


def build_frames():
    teams = pd.read_csv(PROCESSED / "teams.csv")
    team_name = teams.set_index("team")["team_full_name"]
    team_conf = teams.set_index("team")["conf"]
    team_div = teams.set_index("team")["division"]

    standings = pd.read_csv(PROCESSED / "team_standings.csv")
    # Seasons with no games played yet (e.g. 2026 in a preseason pull) are all-zero rows
    standings = standings[standings[["wins", "losses", "ties"]].sum(axis=1) > 0]
    standings.insert(4, "team_full_name", standings["team"].map(team_name))
    standings["made_playoffs"] = standings["seed"].notna().map({True: "Yes", False: "No"})
    standings["playoff"] = standings["playoff"].fillna("Missed")

    games = pd.read_csv(PROCESSED / "games.csv")
    games["surface"] = games["surface"].str.strip()
    games["completed"] = games["completed"].map({True: "Yes", False: "No"})
    games["home_win"] = pd.NA
    played = games["completed"] == "Yes"
    games.loc[played, "home_win"] = (games.loc[played, "result"] > 0).map(
        {True: "Home", False: "Away"})
    games.loc[played & (games["result"] == 0), "home_win"] = "Tie"
    games = games.rename(columns={"home_win": "winner_side"})
    games["gameday"] = pd.to_datetime(games["gameday"])

    weekly = pd.read_csv(PROCESSED / "weekly_team_results.csv")
    weekly["team_full_name"] = weekly["team"].map(team_name)
    weekly["conf"] = weekly["team"].map(team_conf)
    weekly["division"] = weekly["team"].map(team_div)
    weekly["outcome"] = weekly.apply(
        lambda r: "W" if r["win"] else ("L" if r["loss"] else "T"), axis=1)
    weekly["is_home"] = weekly["is_home"].map({True: "Home", False: "Away"})
    weekly = weekly.drop(columns=["win", "loss", "tie"])
    weekly["gameday"] = pd.to_datetime(weekly["gameday"])

    players_raw = pd.read_csv(PROCESSED / "player_stats.csv")
    players = players_raw[list(PLAYER_COLUMNS)].rename(columns=PLAYER_COLUMNS)
    players["Team"] = players["Team"].fillna("FA")
    players["Position"] = players["Position"].fillna("Unknown")
    players.insert(3, "Position Group",
                   players["Position"].map(POSITION_GROUPS).fillna("Other"))
    players.insert(2, "Team Name", players["Team"].map(team_name).fillna("No active roster"))
    players.insert(3, "Conference", players["Team"].map(team_conf).fillna("-"))
    players.insert(4, "Division", players["Team"].map(team_div).fillna("-"))

    frames = {
        "Standings": standings,
        "Games": games,
        "Weekly 2025": weekly,
        "Players 2025": players,
    }

    if FREE_AGENCY_CSV.exists():
        fa = pd.read_csv(FREE_AGENCY_CSV)
        # Same normalization as fetch_player_stats.py: ESPN-style codes -> nflverse
        fa["Team"] = fa["Team"].replace({"LAR": "LA", "WSH": "WAS"})
        fa["Team Name"] = fa["Team"].map(team_name)
        fa["Conference"] = fa["Team"].map(team_conf)
        fa["Total Value ($)"] = money_to_number(fa["total_value"])
        fa["Guarantees ($)"] = money_to_number(fa["guarantees"])
        fa["APY ($)"] = fa["Total Value ($)"] / fa["contract_years"].where(fa["contract_years"] > 0)
        fa["Position Group"] = fa["Position"].map(FA_POSITION_GROUPS).fillna("Other")
        fa = fa.drop(columns=["total_value", "guarantees"]).rename(columns={
            "move_type": "Move Type", "contract_years": "Years", "season": "Season"})
        fa["Move Type"] = fa["Move Type"].fillna("Unknown")
        unmatched = sorted(set(fa.loc[fa["Team Name"].isna(), "Team"]))
        if unmatched:
            print(f"WARNING: free agency team codes not in teams.csv: {unmatched}")
        frames["Free Agency 2026"] = fa

    frames["Teams"] = teams
    frames["Data Dictionary"] = pd.read_csv(PROCESSED / "player_stats_data_dictionary.csv")
    return frames


def table_name(sheet):
    return "tbl" + "".join(ch for ch in sheet.title() if ch.isalnum())


def write_tables(frames, path):
    wb = Workbook()
    readme = wb.active
    readme.title = "README"

    header_fill = PatternFill("solid", fgColor="013369")
    for sheet, df in frames.items():
        ws = wb.create_sheet(sheet)
        ws.append(list(df.columns))
        for row in df.itertuples(index=False):
            ws.append([None if pd.isna(v) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v)
                       for v in row])
        ref = f"A1:{get_column_letter(df.shape[1])}{len(df) + 1}"
        tbl = Table(displayName=table_name(sheet), ref=ref)
        tbl.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        ws.add_table(tbl)
        ws.freeze_panes = "A2"
        for i, col in enumerate(df.columns, start=1):
            letter = get_column_letter(i)
            width = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) + 2
            ws.column_dimensions[letter].width = min(width, 45)
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                for cell in ws[letter][1:]:
                    cell.number_format = "yyyy-mm-dd"
            elif "($)" in col:
                for cell in ws[letter][1:]:
                    cell.number_format = "$#,##0"
        for cell in ws[1]:
            cell.font = Font(name=FONT, bold=True, color="FFFFFF")
            cell.fill = header_fill

    lines = [
        ("NFL Analysis Workbook", True),
        ("Generated by scripts/build_excel_workbook.py from data/processed/*.csv.", False),
        ("", False),
        ("Data sheets (each is an Excel Table, so PivotTables and formulas can reference it by name):", True),
        *[(f"  {s}  ->  {table_name(s)}  ({len(df):,} rows)", False) for s, df in frames.items()],
        ("", False),
        ("Helper columns added for pivoting (filled from teams.csv, not in the source CSVs):", True),
        ("  Standings: team_full_name, made_playoffs (Yes if a seed exists); blank playoff -> 'Missed';", False),
        ("     seasons with no games played yet are left out.", False),
        ("  Games: winner_side (Home/Away/Tie from result = home margin; blank for unplayed games)", False),
        ("  Weekly 2025: team_full_name, conf, division, outcome (W/L/T)", False),
        ("  Players 2025: Team Name, Conference, Division, Position Group (same buckets as the Tableau guide);", False),
        ("     players with no current roster spot show Team = 'FA'. Only the most-used stat columns are kept;", False),
        ("     see data/processed/player_stats.csv for all 100 stat columns.", False),
        ("  Free Agency 2026: dollar text parsed to numbers; APY = Total Value / Years (blank when unknown);", False),
        ("     Position Group = QB/RB/WR/TE/OL/DL/LB/DB/ST.", False),
        ("     Source: nfl_free_agency.db (offseason_moves table). Many moves have no reported value.", False),
        ("", False),
        ("Pivot sheets (start with 'PT -'): drag fields in the PivotTable Fields pane to explore further.", True),
        ("Each pivot sheet has a PivotChart to the right of its slicers; the chart follows the pivot's filters and slicers.", False),
        ("After editing data on a table sheet: Data > Refresh All updates every pivot.", False),
    ]
    for r, (text, bold) in enumerate(lines, start=1):
        c = readme.cell(row=r, column=1, value=text)
        c.font = Font(name=FONT, bold=bold, size=14 if r == 1 else 10)
        c.alignment = Alignment(vertical="top")
    readme.column_dimensions["A"].width = 110

    for ws in wb.worksheets[1:]:
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name=FONT, size=10)

    wb.save(path)
    print(f"Wrote tables -> {path.name}")


# ---------------------------------------------------------------- pivots

XL_DATABASE = 1
XL_ROW, XL_COLUMN, XL_PAGE, XL_DATA = 1, 2, 3, 4
XL_SUM, XL_COUNT, XL_AVERAGE = -4157, -4112, -4106
XL_TOP_COUNT = 1
XL_DESCENDING = 2
XL_TABULAR = 1
XL_RUNNING_TOTAL, XL_PERCENT_OF_ROW = 5, 6
XL_LINE, XL_COLUMN_CLUSTERED, XL_COLUMN_STACKED_100 = 4, 51, 53
XL_BAR_CLUSTERED, XL_BAR_STACKED = 57, 58
XL_CATEGORY, XL_VALUE, XL_SECONDARY = 1, 2, 2
XL_LEGEND_TOP, XL_LEGEND_RIGHT, XL_TICK_LABELS_LOW = -4160, -4152, -4134


def add_pivots(path, has_free_agency):
    import win32com.client as win32

    # Early-bound wrappers: late-bound COM silently drops optional args like
    # After=, which turns Worksheets.Add/Move into "put it in a new workbook"
    excel = win32.gencache.EnsureDispatch(win32.DispatchEx("Excel.Application"))
    excel.Visible = False
    excel.DisplayAlerts = False
    wb = excel.Workbooks.Open(str(path))
    try:
        def pivot(sheet_name, table, title, rows=(), cols=(), filters=(), values=(),
                  slicers=()):
            ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
            ws.Name = sheet_name
            ws.Range("A1").Value = title
            ws.Range("A1").Font.Bold = True
            ws.Range("A1").Font.Size = 14
            cache = wb.PivotCaches().Create(SourceType=XL_DATABASE, SourceData=table)
            pt = cache.CreatePivotTable(TableDestination=ws.Range("A5"),
                                        TableName="pt" + "".join(ch for ch in sheet_name if ch.isalnum()))
            pt.RowAxisLayout(XL_TABULAR)
            pt.RepeatAllLabels(2)  # xlRepeatLabels
            for i, f in enumerate(filters, 1):
                pt.PivotFields(f).Orientation = XL_PAGE
                pt.PivotFields(f).Position = i
            for i, f in enumerate(rows, 1):
                pt.PivotFields(f).Orientation = XL_ROW
                pt.PivotFields(f).Position = i
            for i, f in enumerate(cols, 1):
                pt.PivotFields(f).Orientation = XL_COLUMN
                pt.PivotFields(f).Position = i
            for field, func, caption, fmt in values:
                df = pt.AddDataField(pt.PivotFields(field), caption, func)
                df.NumberFormat = fmt
            for f in rows[:-1]:
                pt.PivotFields(f).Subtotals = (False,) * 12
            left = ws.Range("A1").Left + ws.UsedRange.Width + 30
            for i, f in enumerate(slicers):
                sc = wb.SlicerCaches.Add2(pt, f)
                sc.Slicers.Add(SlicerDestination=ws,
                               Name="slc" + "".join(ch for ch in sheet_name + f if ch.isalnum()),
                               Caption=f, Top=60 + i * 200, Left=left, Width=160, Height=200)
            ws.Columns.AutoFit()
            ws.Range("A1").ColumnWidth = max(ws.Range("A1").ColumnWidth, 14)
            return pt

        def chart(pt, chart_type, title, height=420, width=560, hide=(), horizontal=False,
                  value_format=None, below=False):
            """PivotChart to the right of the pivot and its slicers (or under the
            pivot when `below`). `hide` names data fields to leave off the chart
            (they stay in the pivot)."""
            ws = pt.Parent
            if below:
                left, top = ws.Range("A1").Left, pt.TableRange2.Top + pt.TableRange2.Height + 20
            else:
                left, top = pt.TableRange2.Left + pt.TableRange2.Width, ws.Range("A3").Top
                for shape in ws.Shapes:
                    left = max(left, shape.Left + shape.Width)
                left += 20
            ch = ws.Shapes.AddChart2(-1, chart_type, left, top, width, height).Chart
            ch.SetSourceData(pt.TableRange1)
            ch.HasTitle = True
            ch.ChartTitle.Text = title
            ch.ShowAllFieldButtons = False  # the slicers/report filters do the filtering
            ch.HasLegend = True
            ch.Legend.Position = XL_LEGEND_TOP
            if horizontal:  # bar charts plot bottom-up; match the pivot's top-down order
                ch.Axes(XL_CATEGORY).ReversePlotOrder = True
            if value_format:
                ch.Axes(XL_VALUE).TickLabels.NumberFormat = value_format
            for i in range(ch.SeriesCollection().Count, 0, -1):
                if ch.SeriesCollection(i).Name in hide:
                    ch.SeriesCollection(i).Format.Fill.Visible = False
                    ch.SeriesCollection(i).Format.Line.Visible = False
                    if ch.HasLegend:
                        ch.Legend.LegendEntries(i).Delete()
            if hide:  # let the visible series fill the space the hidden ones would take
                ch.ChartGroups(1).Overlap = 100
                ch.ChartGroups(1).GapWidth = 50
            return ch

        pt = pivot("PT - Wins by Season", "tblStandings",
                   "Wins by team and season (filter by conference; Grand Total = wins since 2021)",
                   rows=("division", "team_full_name"), cols=("season",),
                   filters=("conf",), values=(("wins", XL_SUM, "Wins ", "0"),),
                   slicers=("made_playoffs",))
        chart(pt, XL_BAR_STACKED, "Total wins 2021-2025 (one color per season)",
              height=760, horizontal=True)

        pt = pivot("PT - Playoffs", "tblStandings",
                   "How far each team got: count of seasons by playoff result",
                   rows=("team_full_name",), cols=("playoff",),
                   filters=("conf", "division"),
                   values=(("season", XL_COUNT, "Seasons", "0"),),
                   slicers=("season",))
        result = pt.PivotFields("playoff")
        for pos, item in enumerate(("Missed", "LostWC", "LostDV", "LostCC", "LostSB", "WonSB"), 1):
            result.PivotItems(item).Position = pos
        ch = chart(pt, XL_BAR_STACKED, "Seasons by how far the team got", height=760,
                   horizontal=True)
        ch.SeriesCollection("Missed").Format.Fill.ForeColor.RGB = 0xBFBFBF  # grey: no playoffs

        pt = pivot("PT - Home Field", "tblGames",
                   "Home-field advantage: who won, by venue type (played games only)",
                   rows=("roof",), cols=("winner_side",), filters=("completed", "game_type"),
                   values=(("game_id", XL_COUNT, "Share of Games", "0.0%"),),
                   slicers=("season", "surface"))
        pt.PivotFields("completed").CurrentPage = "Yes"
        pt.DataFields.Item("Share of Games").Calculation = XL_PERCENT_OF_ROW
        chart(pt, XL_COLUMN_STACKED_100, "Who wins, by roof type", height=340)

        # Weeks down the side so the PivotChart draws one line per team across the season
        pt = pivot("PT - 2025 Point Diff", "tblWeekly2025",
                   "2025 season: cumulative point differential by week (pick a division in the slicer to compare 4 teams)",
                   rows=("week",), cols=("team",),
                   filters=("game_type",), values=(("point_diff", XL_SUM, "Cumulative Point Diff", "+0;-0;0"),),
                   slicers=("conf", "division"))
        cumulative = pt.DataFields.Item("Cumulative Point Diff")
        cumulative.Calculation = XL_RUNNING_TOTAL
        cumulative.BaseField = "week"
        pt.ColumnGrand = False  # a running total's grand total is just the last week again
        ch = chart(pt, XL_LINE, "Cumulative point differential, 2025", height=660, width=820,
                   below=True)  # the 32-team pivot is too wide to put the chart beside it
        ch.Legend.Position = XL_LEGEND_RIGHT
        ch.Axes(XL_CATEGORY).TickLabelPosition = XL_TICK_LABELS_LOW  # keep weeks off the zero line

        pt = pivot("PT - Fantasy Leaders", "tblPlayers2025",
                   "Top 10 fantasy scorers (PPR) per position group, 2025",
                   rows=("Position Group", "Player"), filters=("Conference",),
                   values=(("Fantasy PPR", XL_SUM, "PPR Pts", "0.0"),
                           ("Fantasy Half PPR", XL_SUM, "Half PPR Pts", "0.0"),
                           ("Fantasy Std", XL_SUM, "Std Pts", "0.0"),
                           ("Games", XL_SUM, "Games Played", "0")),
                   slicers=("Team Name",))
        pg = pt.PivotFields("Position Group")
        for pos, item in enumerate(("QB", "RB", "WR", "TE", "K"), 1):
            pg.PivotItems(item).Position = pos
        for item in ("DEF/IDP", "Other"):
            try:
                pg.PivotItems(item).Visible = False
            except Exception:
                pass
        player = pt.PivotFields("Player")
        player.AutoSort(XL_DESCENDING, "PPR Pts")
        player.PivotFilters.Add2(Type=XL_TOP_COUNT, DataField=pt.DataFields.Item("PPR Pts"), Value1=10)
        ch = chart(pt, XL_BAR_CLUSTERED, "PPR points, top 10 per position", height=900,
                   horizontal=True, hide=("Half PPR Pts", "Std Pts", "Games Played"))
        ch.HasLegend = False

        if has_free_agency:
            pt = pivot("PT - Free Agency", "tblFreeAgency2026",
                       "2026 offseason: moves and reported money by team",
                       rows=("Team Name",), cols=("Move Type",),
                       filters=("Conference", "Position Group"),
                       values=(("Player", XL_COUNT, "Moves", "0"),),
                       slicers=("Division",))
            chart(pt, XL_BAR_STACKED, "2026 offseason moves by team", height=760, horizontal=True)

            pt = pivot("PT - FA Spending", "tblFreeAgency2026",
                       "2026 offseason: reported contract value by position group (blank values excluded)",
                       rows=("Position Group", "Position"), filters=("Move Type", "Division"),
                       values=(("Total Value ($)", XL_SUM, "Total Value", "$#,##0"),
                               ("APY ($)", XL_AVERAGE, "Avg APY", "$#,##0"),
                               ("Player", XL_COUNT, "Moves", "0")),
                       slicers=("Team Name",))
            pt.PivotFields("Position Group").AutoSort(XL_DESCENDING, "Total Value")
            ch = chart(pt, XL_COLUMN_CLUSTERED, "Reported contract value (bars) and avg APY (line)",
                       height=420, width=640, hide=("Moves",), value_format='$#,##0,,"M"')
            apy = ch.SeriesCollection("Avg APY")
            apy.ChartType = XL_LINE
            apy.AxisGroup = XL_SECONDARY
            ch.Axes(XL_VALUE, XL_SECONDARY).TickLabels.NumberFormat = '$#,##0.0,,"M"'

        # Put the pivots right after README so they're the first thing you see
        n_pivots = sum(1 for s in wb.Worksheets if s.Name.startswith("PT - "))
        for i in range(n_pivots):
            wb.Worksheets(wb.Worksheets.Count - n_pivots + 1 + i).Move(After=wb.Worksheets(1 + i))
        wb.Worksheets("README").Activate()
        wb.Save()
        print(f"Added {n_pivots} PivotTable sheets, each with a PivotChart")
    finally:
        try:
            wb.Close(SaveChanges=False)
            excel.Quit()
        except Exception:
            pass  # Excel already crashed; don't hide the original error


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-pivots", action="store_true",
                        help="only write the data tables (no Excel needed)")
    parser.add_argument("--free-agency-db", type=Path,
                        help="refresh data/processed/offseason_moves_2026.csv from this SQLite DB")
    args = parser.parse_args()

    if args.free_agency_db:
        load_free_agency(args.free_agency_db)
    frames = build_frames()
    write_tables(frames, OUTPUT)
    if not args.no_pivots:
        # Excel automation occasionally fails mid-chart (roughly 1 run in 5);
        # start again from freshly written tables rather than a half-built file
        for attempt in range(1, 4):
            try:
                add_pivots(OUTPUT, "Free Agency 2026" in frames)
                break
            except Exception as exc:
                if attempt == 3:
                    raise
                print(f"Excel step failed ({exc}); retrying ({attempt}/2)")
                write_tables(frames, OUTPUT)


if __name__ == "__main__":
    main()
