# GitHub AI Daily Rising Stars

Daily report generator for the fastest-rising AI-related GitHub repositories, measured by yesterday's new stars.

The scheduled workflow runs every day at 09:30 Asia/Shanghai, reads GH Archive `WatchEvent` data, enriches repositories with the GitHub REST API, asks OpenAI to produce a Chinese analysis, and writes:

- `README.md`
- `reports/YYYY-MM-DD.md`
- `data/YYYY-MM-DD.json`
- `data/latest.json`

## Setup

1. Add repository secret `OPENAI_API_KEY`.
2. Optionally add repository variable `OPENAI_MODEL`; the default is `gpt-5.4-mini`.
3. Enable GitHub Actions for the repository.

## Local Run

Python 3.11 or newer is required.

```bash
python -m pip install -e ".[dev]"
python -m gitpopular run --date 2026-05-25 --timezone Asia/Shanghai --limit 10
```

Use `--candidate-pool` to inspect more rising repositories when fewer than 10 AI projects pass the filters.

## Testing

```bash
pytest
```

The default test suite uses fixtures and mocked clients only; it does not call GitHub, GH Archive, or OpenAI.
