
from server import deps as server_deps


def test_vision_config_reads_model_env(monkeypatch):
    monkeypatch.setenv("VISION_CAMERA_INDEX", "2")
    monkeypatch.setenv("VISION_MODEL_DET", "models/custom_det.onnx")
    monkeypatch.setenv("VISION_MODEL_REC", "models/custom_rec.onnx")
    monkeypatch.setenv("VISION_DET_SCORE", "0.42")
    monkeypatch.setenv("VISION_MATCH_METRIC", "cosine")
    monkeypatch.setenv("VISION_AUTO_DOWNLOAD", "1")
    server_deps.get_config.cache_clear()

    cfg = server_deps.get_config()

    assert cfg.vision_camera_index == 2
    assert cfg.vision_detection_model_path == "models/custom_det.onnx"
    assert cfg.vision_recognition_model_path == "models/custom_rec.onnx"
    assert cfg.vision_detection_score_threshold == 0.42
    assert cfg.vision_match_metric == "cosine"
    assert cfg.vision_auto_download is True


def test_vision_config_reads_bg_env(monkeypatch):
    monkeypatch.setenv("BG_HISTORY", "321")
    monkeypatch.setenv("BG_VAR_THRESHOLD", "40.5")
    monkeypatch.setenv("PEOPLE_MIN_AREA", "9999")
    server_deps.get_config.cache_clear()

    cfg = server_deps.get_config()

    assert cfg.bg_history == 321
    assert cfg.bg_var_threshold == 40.5
    assert cfg.people_min_area == 9999
