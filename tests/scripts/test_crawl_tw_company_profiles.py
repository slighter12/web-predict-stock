from __future__ import annotations


def test_crawl_tw_company_profiles_main_returns_zero(capsys, monkeypatch, load_script):
    module = load_script(
        "crawl_tw_company_profiles.py",
        "crawl_tw_company_profiles_script",
    )
    monkeypatch.setattr(
        module,
        "crawl_tw_company_profiles",
        lambda: {
            "source_name": "tw_company_profiles",
            "raw_payload_id": 1,
            "processed_count": 2,
            "upserted_count": 2,
            "errors": [],
        },
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"upserted_count": 2' in captured.out


def test_crawl_tw_company_profiles_main_returns_one_on_error(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "crawl_tw_company_profiles.py",
        "crawl_tw_company_profiles_script",
    )
    monkeypatch.setattr(
        module,
        "crawl_tw_company_profiles",
        lambda: {
            "source_name": "tw_company_profiles",
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
