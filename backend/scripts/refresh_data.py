"""Refresh all fund data in one go: universe + latest NAVs, then metrics.

Run from the backend folder (needs internet for AMFI and mfapi):
    python -m scripts.refresh_data

Steps:
1. fetch_funds: rebuild the fund universe and download every NAV file again.
2. compute_metrics: recompute every fund's metrics and expense ratio.

The expense ratio file can't be downloaded automatically (see data/README.md),
so this warns when it is more than a month old instead.
"""

from datetime import datetime, timedelta

from scripts import compute_metrics, fetch_funds

TER_MAX_AGE = timedelta(days=35)  # AMFI publishes a new month's TER file monthly


def warn_if_ter_file_is_old() -> None:
    """Print a reminder to download a new TER file when the current one is stale."""
    if not compute_metrics.TER_FILE.exists():
        raise SystemExit(
            f"Missing {compute_metrics.TER_FILE}: download it first (see data/README.md)"
        )
    saved = datetime.fromtimestamp(compute_metrics.TER_FILE.stat().st_mtime)
    if datetime.now() - saved > TER_MAX_AGE:
        print(
            f"Warning: the TER file was saved on {saved:%d %b %Y}. "
            "Download this month's from AMFI (see data/README.md)."
        )


def main() -> None:
    warn_if_ter_file_is_old()
    print("Step 1 of 2: fund universe and NAVs")
    fetch_funds.build_universe(refresh=True)
    print("Step 2 of 2: metrics")
    compute_metrics.main()


if __name__ == "__main__":
    main()
