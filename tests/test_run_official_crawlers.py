from __future__ import annotations


def test_run_lifecycle_crawler_main_returns_zero(capsys, monkeypatch, load_script):
    module = load_script("run_lifecycle_crawler.py", "run_lifecycle_crawler_script")
    monkeypatch.setattr(
        module,
        "crawl_lifecycle_records",
        lambda: {
            "source_name": "tw_official_lifecycle",
            "raw_payload_id": 1,
            "processed_count": 1,
            "upserted_count": 1,
            "errors": [],
        },
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"upserted_count": 1' in captured.out


def test_run_important_event_crawler_main_returns_one_on_error(capsys, monkeypatch, load_script):
    module = load_script(
        "run_important_event_crawler.py",
        "run_important_event_crawler_script",
    )
    monkeypatch.setattr(
        module,
        "crawl_important_events",
        lambda: {
            "source_name": "tw_official_important_event",
            "raw_payload_id": 2,
            "processed_count": 1,
            "upserted_count": 0,
            "errors": ["bad payload"],
        },
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"errors": ["bad payload"]' in captured.out
