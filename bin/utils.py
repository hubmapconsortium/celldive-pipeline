from pathlib import Path
from typing import List, Tuple

import yaml


def make_dir_if_not_exists(dir_path: Path):
    if not dir_path.exists():
        dir_path.mkdir(parents=True)


def path_to_str(path: Path):
    return str(path.absolute().as_posix())


def path_to_str_local(path: Path):
    return str(path.as_posix())


def read_pipeline_config(config_path: Path):
    with open(config_path, "r") as s:
        config = yaml.safe_load(s)
    return config


def save_pipeline_config(config: dict, out_path: Path):
    with open(out_path, "w") as s:
        yaml.safe_dump(config, s)


def get_channel_names_from_ome(xml) -> List[Tuple[str, int]]:
    pixels = xml.find("Image").find("Pixels")
    channels = pixels.findall("Channel")
    ch_names_ids = []
    for ch in channels:
        ch_name = ch.get("Name")
        ch_id_ome = ch.get("ID")  # e.g. Channel:0:12
        ch_id = int(ch_id_ome.split(":")[-1])
        ch_names_ids.append((ch_name, ch_id))
    return ch_names_ids

def get_img_subdir(data_dir: Path)-> Path:
    subdir = data_dir / "lab_processed/images/"
    if subdir.is_dir():
        return subdir
    subdir = data_dir / "HuBMAP_OME/"
    if subdir.is_dir():
        return subdir
    raise ValidationError(f"Directory {data_dir} does not contain subdirectory lab_processed/images/ or HuBMAP_OME/")