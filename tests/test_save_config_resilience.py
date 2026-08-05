from src.utils.config import CONFIG


def test_static_config_exposes_version_through_meta_section():
    assert CONFIG.meta.version == "4.0.3"
