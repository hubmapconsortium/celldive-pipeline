import argparse
from pathlib import Path
from pprint import pprint
from typing import Dict, List

import dask
import tifffile as tif

from utils import (
    make_dir_if_not_exists,
    path_to_str,
    path_to_str_local,
    read_pipeline_config,
)


def create_dirs_per_region(listing: Dict[int, Dict[str, str]], out_dir: Path) -> Dict[int, Path]:
    dirs_per_region = dict()
    dir_name_template = "region_{region:03d}"
    for region in listing:
        dir_path = out_dir / dir_name_template.format(region=region)
        make_dir_if_not_exists(dir_path)
        dirs_per_region[region] = dir_path
    return dirs_per_region


def change_vals_to_keys(input_dict: dict) -> dict:
    vals_to_keys = dict()
    for key, val in input_dict.items():
        vals_to_keys[val] = key
    return vals_to_keys


def extract_segm_channels(path: Path, segm_ch_ids: Dict[str, int]):
    stack = tif.imread(path_to_str(path))
    if len(stack.shape) < 3:
        raise ValueError("Input image is not multichannel")
    segm_channels = dict()
    for ch_name, _id in segm_ch_ids.items():
        segm_channels[ch_name] = stack[_id, ...]
    return segm_channels


def copy_channels(
    out_dir: Path,
    img_path: Path,
    img_slice_name: str,
    segm_ch_index: dict,
    segmentation_channel_ids: Dict[str, int],
):
    new_name_template = "{slice_name}_{segm_ch_type}.tif"
    segm_channels = extract_segm_channels(img_path, segmentation_channel_ids)
    print("segm_channels:")
    pprint(segm_channels)
    for ch_name, img in segm_channels.items():
        segm_ch_type = segm_ch_index[ch_name]
        new_name = new_name_template.format(
            slice_name=img_slice_name,
            segm_ch_type=segm_ch_type,
        )
        dst = out_dir / new_name
        tif.imwrite(dst, img)
        print("channel:", ch_name, "| new_location:", dst)


def copy_segm_channels_to_out_dirs(
    data_dir: Path,
    listing: Dict[int, Dict[str, str]],
    segmentation_channels: Dict[str, str],
    segmentation_channel_ids: Dict[str, int],
    out_dir: Path,
):
    tasks = []
    segm_ch_index = change_vals_to_keys(segmentation_channels)
    for img_slice_name, path in listing.items():
        img_path = data_dir / "3D_image_stack.ome.tiff"
        task = dask.delayed(copy_channels)(
            out_dir,
            img_path,
            img_slice_name,
            segm_ch_index,
            segmentation_channel_ids,
        )
        tasks.append(task)
    dask.compute(*tasks)


def main(data_dir: Path, pipeline_config_path: Path):
    print("data_dir contents:")
    from pprint import pprint

    pprint(list(data_dir.iterdir()))

    pipeline_config = read_pipeline_config(pipeline_config_path)

    segm_ch_out_dir = Path("/output") / "segmentation_channels"
    make_dir_if_not_exists(segm_ch_out_dir)

    listing = pipeline_config["dataset_map_all_slices"]

    segm_ch = pipeline_config["segmentation_channels"]
    segm_ch_ids = pipeline_config["segmentation_channel_ids"]

    dask.config.set({"num_workers": 5, "scheduler": "processes"})

    copy_segm_channels_to_out_dirs(data_dir, listing, segm_ch, segm_ch_ids, segm_ch_out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=Path, help="path to the dataset directory")
    parser.add_argument("--pipeline_config", type=Path, help="path to dataset metadata yaml")
    args = parser.parse_args()

    main(args.data_dir, args.pipeline_config)
