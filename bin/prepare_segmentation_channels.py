import argparse
from pathlib import Path
from typing import Dict, List

import dask
import tifffile as tif
from utils import (
    make_dir_if_not_exists,
    path_to_str,
    path_to_str_local,
    read_pipeline_config,
)


def create_dirs_per_region(
    listing: Dict[int, Dict[str, str]], out_dir: Path
) -> Dict[int, Path]:
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
    dirs_per_region: Dict[int, Path],
    img_path: Path,
    img_slice_name: str,
    region: int,
    segm_ch_index: int,
    segmentation_channel_ids: Dict[str, int],
):
    new_name_template = "reg{region:03d}_{slice_name}_{segm_ch_type}.tif"
    segm_channels = extract_segm_channels(img_path, segmentation_channel_ids)
    for ch_name, img in segm_channels.items():
        segm_ch_type = segm_ch_index[ch_name]
        new_name = new_name_template.format(
            region=region, slice_name=img_slice_name, segm_ch_type=segm_ch_type
        )
        dst = dirs_per_region[region] / new_name
        tif.imwrite(dst, img)
        print("region:", region, "| channel:", ch_name, "| new_location:", dst)


def copy_segm_channels_to_out_dirs(
    data_dir: Path,
    listing: Dict[int, Dict[str, str]],
    segmentation_channels: Dict[str, str],
    segmentation_channel_ids: Dict[str, int],
    dirs_per_region: Dict[int, Path],
):
    tasks = []
    segm_ch_index = change_vals_to_keys(segmentation_channels)
    for region, slices in listing.items():
        for img_slice_name, path in slices.items():
            img_path = data_dir / path
            task = dask.delayed(copy_channels)(
                dirs_per_region,
                img_path,
                img_slice_name,
                region,
                segm_ch_index,
                segmentation_channel_ids,
            )
            tasks.append(task)
    dask.compute(*tasks)


def main(data_dir: Path, pipeline_config_path: Path):
    pipeline_config = read_pipeline_config(pipeline_config_path)

    segm_ch_out_dir = Path("/output") / "segmentation_channels"
    make_dir_if_not_exists(segm_ch_out_dir)

    listing = pipeline_config["dataset_map_all_slices"]

    segm_ch = pipeline_config["segmentation_channels"]
    segm_ch_ids = pipeline_config["segmentation_channel_ids"]

    dask.config.set({"num_workers": 5, "scheduler": "processes"})

    segm_ch_dirs_per_region = create_dirs_per_region(listing, segm_ch_out_dir)

    copy_segm_channels_to_out_dirs(
        data_dir, listing, segm_ch, segm_ch_ids, segm_ch_dirs_per_region
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=Path, help="path to the dataset directory")
    parser.add_argument(
        "--pipeline_config", type=Path, help="path to dataset metadata yaml"
    )
    args = parser.parse_args()

    main(args.data_dir, args.pipeline_config)
