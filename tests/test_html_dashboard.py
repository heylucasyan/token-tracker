import json
from datetime import UTC, datetime
from types import SimpleNamespace

from token_tracker.adapters.types import DailyStats
from token_tracker.html_dashboard import _merge_stats, build_dashboard_data, render_dashboard, write_dashboard


def test_merge_stats_combines_agents_without_projects_or_identifiers():
    stats = [
        DailyStats(
            date="2026-09-15",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_usd=0.1,
            session_count=1,
            message_count=2,
            models={"model-a": 15},
            projects={"/private/project": 15},
            agent_id="codex",
        ),
        DailyStats(
            date="2026-09-15",
            input_tokens=20,
            output_tokens=10,
            total_tokens=30,
            cost_usd=0.2,
            session_count=2,
            message_count=3,
            models={"model-a": 10, "model-b": 20},
            projects={"secret": 30},
            agent_id="claude-code",
        ),
    ]

    rows = _merge_stats(stats, "date")

    assert rows == [
        {
            "key": "2026-09-15",
            "inputTokens": 30,
            "outputTokens": 15,
            "cacheCreationTokens": 0,
            "cacheReadTokens": 0,
            "totalTokens": 45,
            "costUsd": 0.30000000000000004,
            "sessionCount": 3,
            "messageCount": 5,
            "models": {"model-a": 25, "model-b": 20},
        }
    ]
    serialized = json.dumps(rows)
    assert "private" not in serialized
    assert "secret" not in serialized
    assert "agent_id" not in serialized


def test_build_dashboard_data_has_all_periods_for_empty_sources():
    generated_at = datetime(2026, 9, 15, 12, tzinfo=UTC)
    data = build_dashboard_data([(SimpleNamespace(name="Codex"), [])], generated_at=generated_at)

    assert data == {
        "generatedAt": "2026-09-15T12:00:00+00:00",
        "agents": ["Codex"],
        "periods": {"day": [], "week": [], "month": []},
    }


def test_render_dashboard_is_self_contained_and_escapes_script_termination():
    data = {
        "generatedAt": "2026-09-15T12:00:00+08:00",
        "agents": ["Codex"],
        "periods": {
            "day": [{"key": "2026-09-15", "models": {"</script><script>alert(1)</script>": 1}}],
            "week": [],
            "month": [],
        },
    }

    html = render_dashboard(data)

    assert html.startswith("<!doctype html>")
    assert "https://" not in html
    assert "http://" not in html
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script\\u003e" in html


def test_write_dashboard_creates_requested_file(tmp_path):
    path = write_dashboard(
        tmp_path / "dashboard.html",
        {"generatedAt": "now", "agents": [], "periods": {"day": [], "week": [], "month": []}},
    )

    assert path == (tmp_path / "dashboard.html").resolve()
    assert path.read_text(encoding="utf-8").endswith("</html>\n")
