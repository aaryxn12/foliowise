"""Build the fund universe and download NAV history.

Selection rule: every open-ended, direct-plan, growth-option fund in our six
categories that is still active and has at least 5 years of NAV history.
Nothing is hand-picked; the scoring step later ranks each fund against its
whole category.

Sources:
- AMFI's daily NAV file lists every active scheme under its official SEBI
  category, so categories come from AMFI, not from guessing at fund names.
- mfapi.in provides each scheme's full NAV history.

Run from the backend folder:
    python scripts/fetch_funds.py            # reuses NAV files already downloaded
    python scripts/fetch_funds.py --refresh  # downloads every NAV file again

Writes:
    data/fund_universe.csv   funds that passed every check (commit this)
    data/rejected.csv        candidates that failed a check, with the reason
    data/nav/<code>.json     raw NAV history per fund (not committed)
"""

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

AMFI_NAV_FILE = "https://www.amfiindia.com/spages/NAVAll.txt"
MFAPI = "https://api.mfapi.in/mf"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NAV_DIR = DATA_DIR / "nav"

MIN_HISTORY_YEARS = 5
MAX_DAYS_SINCE_LAST_NAV = 30  # older than this means the fund is closed or merged
REQUEST_PAUSE_SECONDS = 0.2  # be polite to a free, community-run API
RETRIES = 3
INDIA = ZoneInfo("Asia/Kolkata")  # NAV dates are Indian dates


@dataclass(frozen=True)
class CategoryRule:
    """How to recognise one of our categories in AMFI's list.

    `amfi_categories` are AMFI's official category names for it, compared
    loosely. AMFI's file uses more than one heading for some categories (e.g.
    "Debt Scheme - Corporate Bond Fund" and "Income/Debt Oriented Schemes -
    Corporate Bond Fund"), so a rule can list several. Index funds and gold
    fund-of-funds share broad AMFI categories with many other funds, so those
    two also need a name pattern.
    """

    amfi_categories: tuple[str, ...]
    name_pattern: str = ""
    name_excludes: str = ""


CATEGORY_RULES = {
    "large_cap_index": CategoryRule(
        amfi_categories=("Other Scheme - Index Funds", "Index Funds - Equity Funds"),
        name_pattern=r"nifty\s*50\b|\bnifty index fund\b",  # SBI omits the "50"
        name_excludes=r"next|equal|value|shariah|alpha|low vol|momentum|quality",
    ),
    "flexi_cap": CategoryRule(amfi_categories=("Equity Scheme - Flexi Cap Fund",)),
    "mid_cap": CategoryRule(amfi_categories=("Equity Scheme - Mid Cap Fund",)),
    "small_cap": CategoryRule(amfi_categories=("Equity Scheme - Small Cap Fund",)),
    "debt": CategoryRule(
        amfi_categories=(
            "Debt Scheme - Corporate Bond Fund",
            "Income/Debt Oriented Schemes - Corporate Bond Fund",
        )
    ),
    "gold": CategoryRule(
        amfi_categories=(
            "Other Scheme - FoF Domestic",
            "Fund of Funds Scheme (Domestic) - Fund of Funds Scheme (Domestic)",
        ),
        name_pattern=r"\bgold\b",
        name_excludes=r"silver|multi|asset",
    ),
}

DIRECT = re.compile(r"\bdirect\b", re.IGNORECASE)
GROWTH = re.compile(r"growth|cumulative", re.IGNORECASE)
NOT_GROWTH = re.compile(r"idcw|dividend|payout|reinvest|bonus|regular", re.IGNORECASE)
SECTION_HEADING = re.compile(r"^Open Ended Schemes\s*\((.+)\)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Scheme:
    code: int
    name: str
    amfi_category: str
    plan: str = ""  # e.g. "Direct Plan"; empty when the file puts it in the name
    option: str = ""  # e.g. "Growth" or "IDCW"

    @property
    def full_name(self) -> str:
        """Name with plan and option, e.g. "X Fund - Direct Plan - Growth"."""
        return " - ".join(part for part in (self.name, self.plan, self.option) if part)


def fetch(url: str) -> bytes:
    """GET a URL, retrying briefly on network errors."""
    request = urllib.request.Request(url, headers={"User-Agent": "FolioWise/0.1"})
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == RETRIES:
                raise
            print(f"  retry {attempt} for {url}: {error}")
            time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def normalise_category(text: str) -> str:
    """Compare categories loosely: AMFI writes both "Equity Scheme - X" and
    "Equity Schemes - X", and sometimes doubles spaces."""
    text = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"\bschemes\b", "scheme", text)


def parse_amfi_nav_file(text: str) -> list[Scheme]:
    """Every open-ended scheme in AMFI's NAV file, with its official category.

    The file is a series of sections. A heading line such as
    "Open Ended Schemes(Equity Scheme - Mid Cap Fund)" is followed by
    fund-house names and ";"-separated scheme lines. Columns are found from
    the file's own header line ("Scheme Code;...;Scheme Name;Plan;Option;...")
    instead of being assumed: older layouts put plan and option inside the
    name, the current one has separate Plan and Option columns.
    """
    schemes = []
    seen_codes = set()
    category = None
    columns = {"scheme name": 3}
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("scheme code"):
            headers = [header.strip().lower() for header in line.split(";")]
            columns = {header: i for i, header in enumerate(headers)}
            continue
        heading = SECTION_HEADING.match(line)
        if heading:
            category = heading.group(1).strip()
            continue
        if line.lower().startswith(("close ended", "interval fund")):
            category = None  # we only use open-ended schemes
            continue
        fields = [field.strip() for field in line.split(";")]
        if not (category and len(fields) >= len(columns)):
            continue
        code = fields[0]
        if code.isdigit() and int(code) not in seen_codes:
            seen_codes.add(int(code))
            schemes.append(
                Scheme(
                    code=int(code),
                    name=_column(fields, columns, "scheme name"),
                    amfi_category=category,
                    plan=_column(fields, columns, "plan"),
                    option=_column(fields, columns, "option"),
                )
            )
    return schemes


def _column(fields: list[str], columns: dict[str, int], header: str) -> str:
    """The value under `header`, or "" if the file has no such column."""
    index = columns.get(header)
    return fields[index] if index is not None and index < len(fields) else ""


def is_direct_growth(scheme: Scheme) -> bool:
    """True for a direct-plan, growth-option scheme.

    Uses the Plan and Option columns when the file has them, otherwise the name.
    """
    plan = scheme.plan or scheme.name
    option = scheme.option or scheme.name
    return bool(
        DIRECT.search(plan) and GROWTH.search(option) and not NOT_GROWTH.search(option)
    )


def our_category(scheme: Scheme) -> str | None:
    """Our category for a scheme, or None if it fits none of them."""
    for category, rule in CATEGORY_RULES.items():
        wanted = {normalise_category(name) for name in rule.amfi_categories}
        if normalise_category(scheme.amfi_category) not in wanted:
            continue
        if rule.name_pattern and not re.search(
            rule.name_pattern, scheme.name, re.IGNORECASE
        ):
            continue
        if rule.name_excludes and re.search(
            rule.name_excludes, scheme.name, re.IGNORECASE
        ):
            continue
        return category
    return None


def parse_nav_date(text: str) -> date:
    """mfapi dates look like 21-11-2026."""
    return datetime.strptime(text, "%d-%m-%Y").replace(tzinfo=INDIA).date()


def check_history(nav_rows: list[dict], today: date) -> str | None:
    """Return why the NAV history is not usable, or None if it is fine."""
    if not nav_rows:
        return "no NAV history"
    newest = parse_nav_date(nav_rows[0]["date"])  # mfapi lists newest first
    oldest = parse_nav_date(nav_rows[-1]["date"])
    if (today - newest).days > MAX_DAYS_SINCE_LAST_NAV:
        return f"no NAV since {newest} (closed or merged)"
    if oldest > today - timedelta(days=round(365.25 * MIN_HISTORY_YEARS)):
        return f"history starts {oldest}, under {MIN_HISTORY_YEARS} years"
    return None


def load_nav(code: int, refresh: bool) -> dict:
    """Full NAV history for one scheme, from the local copy when possible."""
    path = NAV_DIR / f"{code}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    payload = json.loads(fetch(f"{MFAPI}/{code}"))
    time.sleep(REQUEST_PAUSE_SECONDS)
    path.write_text(json.dumps(payload))
    return payload


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_universe(refresh: bool) -> None:
    NAV_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(INDIA).date()

    print("Downloading AMFI's list of all schemes...")
    schemes = parse_amfi_nav_file(fetch(AMFI_NAV_FILE).decode("utf-8", "replace"))
    candidates = [
        (scheme, category)
        for scheme in schemes
        if is_direct_growth(scheme) and (category := our_category(scheme))
    ]
    print(f"{len(schemes)} open-ended schemes, {len(candidates)} candidates to check")

    found = Counter(category for _, category in candidates)
    for category, rule in CATEGORY_RULES.items():
        if found[category]:
            continue
        wanted = {normalise_category(name) for name in rule.amfi_categories}
        examples = [
            s.full_name
            for s in schemes
            if normalise_category(s.amfi_category) in wanted
        ]
        print(f"  WARNING: no candidates for {category} {rule.amfi_categories}.")
        print(f"    AMFI lists {len(examples)} schemes there, for example:")
        for name in examples[:3]:
            print(f"      {name!r}")

    accepted, rejected = [], []
    for number, (scheme, category) in enumerate(candidates, start=1):
        print(f"[{number}/{len(candidates)}] {scheme.full_name}")
        try:
            payload = load_nav(scheme.code, refresh)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            rejected.append((scheme, category, f"download failed: {error}"))
            continue

        rows = payload.get("data", [])
        reason = check_history(rows, today)
        if reason:
            rejected.append((scheme, category, reason))
            (NAV_DIR / f"{scheme.code}.json").unlink(missing_ok=True)
            continue

        accepted.append(
            {
                "scheme_code": scheme.code,
                "scheme_name": scheme.full_name,
                "category": category,
                "fund_house": payload.get("meta", {}).get("fund_house", ""),
                "first_nav_date": parse_nav_date(rows[-1]["date"]).isoformat(),
                "latest_nav_date": parse_nav_date(rows[0]["date"]).isoformat(),
                "fetched_on": today.isoformat(),
            }
        )

    write_csv(DATA_DIR / "fund_universe.csv", accepted)
    write_csv(
        DATA_DIR / "rejected.csv",
        [
            {
                "scheme_code": scheme.code,
                "scheme_name": scheme.full_name,
                "category": category,
                "reason": reason,
            }
            for scheme, category, reason in rejected
        ],
    )

    print(f"\nAccepted {len(accepted)} funds, rejected {len(rejected)}:")
    for category in CATEGORY_RULES:
        count = sum(1 for fund in accepted if fund["category"] == category)
        print(f"  {category:<16} {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--refresh", action="store_true", help="download every NAV file again"
    )
    build_universe(refresh=parser.parse_args().refresh)


if __name__ == "__main__":
    main()
