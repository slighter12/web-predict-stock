from __future__ import annotations


def test_dispatch_scheduled_ingestions_main_returns_zero(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "dispatch_scheduled_ingestions.py",
        "dispatch_scheduled_ingestions_script",
    )
    monkeypatch.setattr(
        module,
        "dispatch_due_scheduled_ingestions",
        lambda: {
            "schedule_count": 1,
            "dispatched_count": 1,
            "succeeded_count": 1,
            "failed_count": 0,
            "skipped_count": 0,
            "records": [],
        },
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"succeeded_count": 1' in captured.out


def test_dispatch_scheduled_ingestions_main_returns_one_on_failure(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "dispatch_scheduled_ingestions.py",
        "dispatch_scheduled_ingestions_script",
    )
    monkeypatch.setattr(
        module,
        "dispatch_due_scheduled_ingestions",
        lambda: {
            "schedule_count": 1,
            "dispatched_count": 1,
            "succeeded_count": 0,
            "failed_count": 1,
            "skipped_count": 0,
            "records": [],
        },
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"failed_count": 1' in captured.out
