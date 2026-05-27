from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .archive import parse_report_date
from .pipeline import PipelineConfig, collect_raw_report, finalize_report_from_analysis, run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gitpopular", description="Generate a daily GitHub AI rising-stars report.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Generate the report for a date.")
    run_parser.add_argument("--date", help="Report date in local timezone, YYYY-MM-DD. Defaults to yesterday.")
    run_parser.add_argument("--timezone", default="Asia/Shanghai", help="IANA timezone for the report day.")
    run_parser.add_argument("--limit", type=int, default=10, help="Number of repositories to include.")
    run_parser.add_argument("--candidate-pool", type=int, default=100, help="Top star-growth candidates to inspect.")
    run_parser.add_argument("--min-ai-confidence", type=float, default=0.55, help="Minimum model AI confidence.")
    run_parser.add_argument("--output", type=Path, default=Path("."), help="Output repository root.")
    run_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Write a report even when fewer than --limit projects pass the filters.",
    )

    collect_parser = subparsers.add_parser("collect", help="Collect raw star-growth and README data without AI API calls.")
    collect_parser.add_argument("--date", help="Report date in local timezone, YYYY-MM-DD. Defaults to yesterday.")
    collect_parser.add_argument("--timezone", default="Asia/Shanghai", help="IANA timezone for the report day.")
    collect_parser.add_argument("--limit", type=int, default=10, help="Number of repositories to include.")
    collect_parser.add_argument("--candidate-pool", type=int, default=150, help="Top star-growth candidates to inspect.")
    collect_parser.add_argument("--output", type=Path, default=Path("."), help="Output repository root.")
    collect_parser.add_argument("--readme-char-limit", type=int, default=80_000, help="Maximum README characters per repo.")
    collect_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Write raw data even when fewer than --limit projects pass the filters.",
    )

    finalize_parser = subparsers.add_parser("finalize", help="Render final report from raw data and Codex analysis JSON.")
    finalize_parser.add_argument("--date", required=True, help="Report date, YYYY-MM-DD.")
    finalize_parser.add_argument("--output", type=Path, default=Path("."), help="Output repository root.")
    finalize_parser.add_argument(
        "--analysis-file",
        type=Path,
        help="Analysis JSON path. Defaults to data/analysis/YYYY-MM-DD.json under --output.",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        report_date = parse_report_date(args.date) if args.date else _yesterday(args.timezone)
        config = PipelineConfig(
            report_date=report_date,
            timezone=args.timezone,
            limit=args.limit,
            candidate_pool=args.candidate_pool,
            min_ai_confidence=args.min_ai_confidence,
            require_exact_limit=not args.allow_partial,
            output_root=args.output,
        )
        report = run_pipeline(config)
        print(f"Wrote {len(report.items)} items for {report.date} to {args.output}")
        return 0

    if args.command == "collect":
        report_date = parse_report_date(args.date) if args.date else _yesterday(args.timezone)
        config = PipelineConfig(
            report_date=report_date,
            timezone=args.timezone,
            limit=args.limit,
            candidate_pool=args.candidate_pool,
            require_exact_limit=not args.allow_partial,
            output_root=args.output,
            readme_char_limit=args.readme_char_limit,
        )
        report = collect_raw_report(config)
        print(f"Collected {len(report.items)} raw items for {report.date} to {args.output}")
        return 0

    if args.command == "finalize":
        report_date = parse_report_date(args.date)
        report = finalize_report_from_analysis(
            report_date=report_date,
            output_root=args.output,
            analysis_path=args.analysis_file,
        )
        print(f"Finalized {len(report.items)} analyzed items for {report.date} to {args.output}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _yesterday(timezone_name: str) -> date:
    tz = ZoneInfo(timezone_name)
    return (datetime.now(tz).date() - timedelta(days=1))
