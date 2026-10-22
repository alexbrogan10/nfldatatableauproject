"""
Generates a starter Tableau workbook (.twb) that pre-connects all of the
processed CSVs with explicit column types, so opening the project in
Tableau skips the manual "browse & connect" step and avoids relying on
Tableau's CSV type auto-detection (which sometimes misreads things like
zero-padded IDs or boolean columns).

This intentionally only wires up data source connections — no worksheets
or dashboards. Tableau's text-file connection metadata format isn't fully
documented, and hand-authoring worksheet XML without a Tableau install to
verify against is a much higher-risk exercise than the data source blocks
here (which Tableau re-validates against the actual CSV on open anyway,
same as it does for any text-file connection). Build sheets in the app
following docs/tableau_guide.md.
"""
import re
import uuid
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed"
OUT_FILE = REPO_ROOT / "NFL_Dashboard_Starter.twb"

# Files to wire up as data sources (data dictionary is documentation, not
# meant to be related to the others, so it's left out here).
FILES = ["games", "team_standings", "weekly_team_results", "player_stats", "teams"]

# Columns that are dates but round-trip through CSV as plain strings.
DATE_COLUMNS = {"gameday"}

# (local-type, remote-type, role, semantic-type) per pandas dtype.
TYPE_MAP = {
    "int64": ("integer", "20", "dimension", "ordinal"),
    "float64": ("real", "5", "measure", "quantitative"),
    "bool": ("boolean", "11", "dimension", "nominal"),
    "object": ("string", "130", "dimension", "nominal"),
    "str": ("string", "130", "dimension", "nominal"),
    "date": ("date", "133", "dimension", "ordinal"),
}


def short_id() -> str:
    return uuid.uuid4().hex[:16]


def xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&apos;")
    )


def column_type(df: pd.DataFrame, col: str) -> tuple[str, str, str, str]:
    if col in DATE_COLUMNS:
        return TYPE_MAP["date"]
    return TYPE_MAP[str(df[col].dtype)]


def build_datasource(stem: str) -> str:
    df = pd.read_csv(DATA_DIR / f"{stem}.csv")
    filename = f"{stem}.csv"
    federated_name = f"federated.{short_id()}"
    textscan_name = f"textscan.{short_id()}"
    relation_table = f"[{stem}#csv]"
    relation_name = filename

    metadata_records = []
    columns = []
    for col in df.columns:
        local_type, remote_type, role, semantic_type = column_type(df, col)
        aggregation = "Sum" if role == "measure" else "Count"
        col_escaped = xml_escape(col)
        metadata_records.append(f"""        <metadata-record class='column'>
          <remote-name>{col_escaped}</remote-name>
          <remote-type>{remote_type}</remote-type>
          <local-name>[{col_escaped}]</local-name>
          <parent-name>[{xml_escape(relation_name)}]</parent-name>
          <remote-alias>{col_escaped}</remote-alias>
          <local-type>{local_type}</local-type>
          <aggregation>{aggregation}</aggregation>
          <contains-null>true</contains-null>
        </metadata-record>""")
        columns.append(
            f"    <column caption='{col_escaped}' datatype='{local_type}' "
            f"name='[{col_escaped}]' role='{role}' type='{semantic_type}' />"
        )

    metadata_block = "\n".join(metadata_records)
    columns_block = "\n".join(columns)

    return f"""  <datasource caption='{xml_escape(stem)}' inline='true' name='{federated_name}' version='18.1'>
    <connection class='federated'>
      <named-connections>
        <named-connection caption='{xml_escape(filename)}' name='{textscan_name}'>
          <connection class='textscan' directory='data/processed' filename='{xml_escape(filename)}' password='' server='' />
        </named-connection>
      </named-connections>
      <relation connection='{textscan_name}' name='{xml_escape(relation_name)}' table='{xml_escape(relation_table)}' type='table'>
      </relation>
      <metadata-records>
{metadata_block}
      </metadata-records>
    </connection>
    <aliases enabled='yes' />
{columns_block}
  </datasource>"""


def main() -> None:
    datasource_blocks = [build_datasource(stem) for stem in FILES]
    datasources_xml = "\n".join(datasource_blocks)

    workbook = f"""<?xml version='1.0' encoding='utf-8' ?>

<!-- NFL data pre-connected for Tableau. See docs/tableau_guide.md for the
     join keys between these data sources and a suggested dashboard build-out.
     No worksheets or dashboards are included; build those in Tableau. -->
<workbook source-build='2023.1.0' source-platform='mac' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
  </preferences>
  <datasources>
{datasources_xml}
  </datasources>
</workbook>
"""

    OUT_FILE.write_text(workbook, encoding="utf-8")
    print(f"wrote {OUT_FILE.relative_to(REPO_ROOT)} with {len(FILES)} data sources")


if __name__ == "__main__":
    main()
