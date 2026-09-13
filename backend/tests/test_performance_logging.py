from app.services.performance_logging import identify_bottleneck, log_stage


def test_log_stage_appends_to_log_and_csv(tmp_path):
    log_stage(tmp_path, "run_1", "profiling", 0.4321)
    log_stage(tmp_path, "run_1", "issue_detection", 0.1234)

    log_text = (tmp_path / "performance.log").read_text(encoding="utf-8")
    assert "run_id=run_1" in log_text
    assert "stage=profiling" in log_text
    assert "seconds=0.4321" in log_text
    assert "stage=issue_detection" in log_text

    csv_text = (tmp_path / "performance_log.csv").read_text(encoding="utf-8")
    lines = csv_text.strip().splitlines()
    assert lines[0] == "timestamp,run_id,stage,seconds"
    assert len(lines) == 3  # header + 2 rows
    assert "profiling" in lines[1]
    assert "issue_detection" in lines[2]


def test_log_stage_appends_without_overwriting_existing_rows(tmp_path):
    log_stage(tmp_path, "run_1", "upload", 0.1)
    log_stage(tmp_path, "run_2", "upload", 0.2)

    csv_text = (tmp_path / "performance_log.csv").read_text(encoding="utf-8")
    lines = csv_text.strip().splitlines()
    assert len(lines) == 3  # header + 2 runs, both preserved
    assert "run_1" in lines[1]
    assert "run_2" in lines[2]


def test_identify_bottleneck_returns_max_stage():
    times = {"file_loading": 0.5, "profiling": 4.2, "issue_detection": 1.1}
    assert identify_bottleneck(times) == {"stage": "profiling", "seconds": 4.2}


def test_identify_bottleneck_empty_returns_none():
    assert identify_bottleneck({}) is None


def test_identify_bottleneck_single_stage():
    assert identify_bottleneck({"cleaning": 2.0}) == {"stage": "cleaning", "seconds": 2.0}
