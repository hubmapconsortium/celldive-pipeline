import argparse
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Tuple, Union

import tifffile as tif
import yaml
from dataset_path_arrangement import create_listing_for_each_region
from utils import (
    get_channel_names_from_ome,
    get_img_subdir,
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
    path: Path,
    segm_ch_names: Dict[str, Union[str, List[str]]],
) -> Tuple[Dict[str, int], Dict[str, str]]:
    """
    Returns a 2-tuple:
     [0] Mapping from segmentation channel names to 0-based indexes into channel list
     [1] Adjustment of segm_ch_names listing the first segmentation channel found
    """
    with tif.TiffFile(path_to_str(path)) as TF:
        ome_meta = TF.ome_metadata
    ome_xml = strip_namespace(ome_meta)
    ch_names_ids = get_channel_names_from_ome(ome_xml)
    segm_ch_names_ids: Dict[str, int] = {}
    adj_segm_ch_names: Dict[str, str] = {}
    for ch_type, name_or_names in segm_ch_names.items():
        found = False
        if isinstance(name_or_names, str):
            name_or_names = [name_or_names]
        for name_to_search in name_or_names:
            if found:
                break
            for ch_name, ch_id in ch_names_ids:
                print("Checking", ch_name, "against", name_to_search)
                if found := fnmatch(ch_name, name_to_search):
                    print("Matched", ch_name, "against", name_to_search)
                    segm_ch_names_ids[ch_name] = ch_id
                    adj_segm_ch_names[ch_type] = ch_name
                    break
        if not found:
            raise KeyError(f"Couldn't find channel {ch_type} in any of {name_or_names}")
    return segm_ch_names_ids, adj_segm_ch_names


def get_first_img_path(data_dir: Path, listing: Dict[int, Dict[str, Path]]) -> Path:
    first_region = min(list(listing.keys()))
    first_img_path = list(listing[first_region].values())[0]
    return Path(data_dir / first_img_path).absolute()


def main(data_dir: Path, meta_path: Path):
    data_dir = get_img_subdir(data_dir)
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
    segm_ch_names_ids, adj_segmentation_channels = get_segm_channel_ids_from_ome(
        first_img_path, segmentation_channels
    )

    listing_str = convert_all_paths_to_str(listing)

    pipeline_config = dict()
    pipeline_config["segmentation_channels"] = adj_segmentation_channels
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
