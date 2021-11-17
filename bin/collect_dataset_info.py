import argparse
from pathlib import Path
from typing import Dict, List

import tifffile as tif
import yaml
from dataset_path_arrangement import create_listing_for_each_region
from utils import (
    get_channel_names_from_ome,
    make_dir_if_not_exists,
    path_to_str,
    path_to_str_local,
    save_pipeline_config,
)
from utils_ome import strip_namespace


def read_meta(meta_path: Path) -> dict:
    with open(meta_path, "r") as s:
        meta = yaml.safe_load(s)
    return meta


def convert_all_paths_to_str(listing: dict) -> Dict[int, Dict[str, str]]:
    all_ch_dirs = dict()
    for region, dir_path in listing.items():
        all_ch_dirs[region] = dict()
        for channel_name, ch_path in listing[region].items():
            all_ch_dirs[region][channel_name] = path_to_str_local(ch_path)
    return all_ch_dirs


def get_segm_channel_ids_from_ome(
    path: Path, segm_ch_names: Dict[str, str]
) -> Dict[str, int]:
    with tif.TiffFile(path_to_str(path)) as TF:
        ome_meta = TF.ome_metadata
    ome_xml = strip_namespace(ome_meta)
    ch_names_ids = get_channel_names_from_ome(ome_xml)
    segm_ch_names_ids = dict()
    for ch_type, name in segm_ch_names.items():
        segm_ch_names_ids[name] = ch_names_ids[name]
    return segm_ch_names_ids


def get_first_img_path(data_dir: Path, listing: Dict[int, Dict[str, Path]]) -> Path:
    first_region = min(list(listing.keys()))
    first_img_path = list(listing[first_region].values())[0]
    return Path(data_dir / first_img_path).absolute()


def main(data_dir: Path, meta_path: Path):
    meta = read_meta(meta_path)
    segmentation_channels = meta["segmentation_channels"]

    listing = create_listing_for_each_region(data_dir)
    if listing == {}:
        raise ValueError(
            "Dataset directory is either empty or has unexpected structure"
        )

    out_dir = Path("/output")
    make_dir_if_not_exists(out_dir)

    first_img_path = data_dir / get_first_img_path(data_dir, listing)
    segm_ch_names_ids = get_segm_channel_ids_from_ome(
        first_img_path, segmentation_channels
    )

    listing_str = convert_all_paths_to_str(listing)

    pipeline_config = dict()
    pipeline_config["segmentation_channels"] = segmentation_channels
    pipeline_config["dataset_map_all_slices"] = listing_str
    pipeline_config["segmentation_channel_ids"] = segm_ch_names_ids

    pipeline_config_path = out_dir / "pipeline_config.yaml"
    save_pipeline_config(pipeline_config, pipeline_config_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=Path, help="path to the dataset directory")
    parser.add_argument("--meta_path", type=Path, help="path to dataset metadata yaml")
    args = parser.parse_args()

    main(args.data_dir, args.meta_path)
