from __future__ import annotations


def test_run_scheduled_recovery_drills_main_returns_zero(capsys, monkeypatch, load_script):
    module = load_script(
        "run_scheduled_recovery_drills.py",
        "run_scheduled_recovery_drills_script",
    )
    monkeypatch.setattr(
        module,
        "dispatch_due_recovery_drills",
        lambda: {
            "schedule_count": 1,
            "dispatched_count": 1,
            "succeeded_count": 1,
            "failed_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "records": [],
            "errors": [],
        },
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"succeeded_count": 1' in captured.out


def test_run_scheduled_recovery_drills_main_returns_one_on_failure(capsys, monkeypatch, load_script):
    module = load_script(
        "run_scheduled_recovery_drills.py",
        "run_scheduled_recovery_drills_script",
    )
    monkeypatch.setattr(
        module,
        "dispatch_due_recovery_drills",
        lambda: {
            "schedule_count": 1,
            "dispatched_count": 1,
            "succeeded_count": 0,
            "failed_count": 1,
            "skipped_count": 0,
            "error_count": 0,
            "records": [],
            "errors": [],
        },
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"failed_count": 1' in captured.out
