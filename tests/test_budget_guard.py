from pathlib import Path
import datetime as _dt

from stock_chatter import cli
from stock_chatter.io_utils import append_jsonl, write_json


def test_fetch_x_daily_budget_guard_stops_before_network(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "fetch_recent_cashtag_posts", lambda **kwargs: (_ for _ in ()).throw(AssertionError("network")))
    result = cli.main(["fetch-x", "--approve-x-cost", "--daily-budget-usd", "0.49"])
    assert result == 2
    assert "No X API call was made" in capsys.readouterr().out
    assert not Path("data/raw/x_posts.jsonl").exists()


def test_fetch_x_does_not_charge_budget_on_failed_fetch(tmp_path, monkeypatch):
    # A failed fetch must not leave a phantom charge that blocks later runs;
    # the daily budget is debited only after a successful call.
    monkeypatch.chdir(tmp_path)

    def fail_network(**kwargs):
        raise RuntimeError("unexpected network failure")

    monkeypatch.setattr(cli, "fetch_recent_cashtag_posts", fail_network)
    try:
        cli.main(["fetch-x", "--approve-x-cost"])
    except RuntimeError:
        pass
    state_files = list(Path("data/state").glob("monitor_state.json"))
    if state_files:
        assert "x_estimated_spend_usd_" not in state_files[0].read_text()


def test_fetch_x_stops_when_budget_already_used(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_json("data/state/monitor_state.json", {"x_estimated_spend_usd_2026-05-07": "1.00"})
    monkeypatch.setattr(cli, "datetime", _FrozenDatetime)
    monkeypatch.setattr(cli, "fetch_recent_cashtag_posts", lambda **kwargs: (_ for _ in ()).throw(AssertionError("network")))
    result = cli.main(["fetch-x", "--approve-x-cost", "--daily-budget-usd", "1"])
    assert result == 2
    assert "budget guard stopped" in capsys.readouterr().out


def test_fetch_x_window_counts_against_current_run_day(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "datetime", _FrozenDatetime)
    monkeypatch.setattr(cli, "fetch_recent_cashtag_posts", lambda **kwargs: [])
    result = cli.main(
        [
            "fetch-x",
            "--start-time",
            "2026-05-01T00:00:00Z",
            "--end-time",
            "2026-05-02T00:00:00Z",
            "--approve-x-cost",
        ]
    )
    assert result == 0
    state = Path("data/state/monitor_state.json").read_text()
    assert "x_estimated_spend_usd_2026-05-07" in state
    assert "x_estimated_spend_usd_2026-05-02" not in state


def test_fetch_x_clamps_stale_since_last_cursor_to_7_day_floor(tmp_path, monkeypatch):
    # A --since-last cursor older than X's 7-day recent-search window must be
    # clamped forward so the request isn't rejected with HTTP 400.
    monkeypatch.chdir(tmp_path)
    write_json("data/state/monitor_state.json", {"last_x_fetch_at": "2026-01-01T00:00:00Z"})
    monkeypatch.setattr(cli, "datetime", _FrozenDatetime)
    captured = {}
    monkeypatch.setattr(
        cli,
        "fetch_recent_cashtag_posts",
        lambda **kwargs: captured.update(kwargs) or [],
    )
    result = cli.main(["fetch-x", "--since-last", "--approve-x-cost"])
    assert result == 0
    floor = _dt.datetime(2026, 4, 30, 12, 15, tzinfo=_dt.timezone.utc)
    assert captured["start_time"] == floor


def test_repair_state_sets_watermark_to_max_saved_post(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    append_jsonl(
        "data/raw/x_posts.jsonl",
        [
            {"id": "1", "created_at": "2026-05-06T00:00:00Z"},
            {"id": "2", "created_at": "2026-05-07T01:44:53Z"},
        ],
    )
    assert cli.main(["repair-state"]) == 0
    state = Path("data/state/monitor_state.json").read_text()
    assert "2026-05-07T01:44:53Z" in state


class _FrozenDatetime(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return _dt.datetime(2026, 5, 7, 12, 0, tzinfo=tz)
