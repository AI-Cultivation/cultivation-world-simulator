from omegaconf import OmegaConf

from src.utils.config import CONFIG, get_static_config_path


def test_static_config_exposes_version_through_meta_section():
    source_config = OmegaConf.load(get_static_config_path())

    assert CONFIG.meta.version == source_config.meta.version
