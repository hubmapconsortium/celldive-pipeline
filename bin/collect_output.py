import argparse
import shutil
from pathlib import Path
from typing import Dict, Iterable
from os import walk
import re
import dask
import numpy as np
import tifffile as tif
from utils import get_img_subdir, make_dir_if_not_exists, path_to_str, read_pipeline_config
from utils_ome import modify_initial_ome_meta

ome_tiff_pattern = re.compile(r"(?P<basename>.*)\.ome\.tiff(f?)$")

def find_ome_tiff(input_dir: Path) -> Path:
    """
    Yields 2-tuples:
     [0] full Path to source file
     [1] output file Path (source file relative to input_dir)
    """
    for dirpath_str, _, filenames in walk(input_dir):
        dirpath = Path(dirpath_str)
        for filename in filenames:
            if ome_tiff_pattern.match(filename):
                src_filepath = dirpath / filename
                return src_filepath

Image = np.ndarray


def add_z_axis(img_stack: Image):
    stack_shape = img_stack.shape
    new_stack_shape = [stack_shape[0], 1, stack_shape[1], stack_shape[2]]
    return img_stack.reshape(new_stack_shape)


def modify_and_save_img(
    img_path: Path, out_path: Path, segmentation_channels: Dict[str, str]
):
    with tif.TiffFile(path_to_str(img_path)) as TF:
        ome_meta = TF.ome_metadata
        img_stack = TF.series[0].asarray()
    new_img_stack = add_z_axis(img_stack)
    new_ome_meta = modify_initial_ome_meta(ome_meta, segmentation_channels)
    with tif.TiffWriter(path_to_str(out_path), bigtiff=True) as TW:
        TW.write(
            new_img_stack,
            contiguous=True,
            photometric="minisblack",
            description=new_ome_meta,
        )


def copy_files(
    file_type: str,
    src_data_dir: Path,
    src_dir_name: str,
    img_name_template: str,
    out_dir: Path,
    out_name_template: str,
    region: int,
    slices: Dict[str, str],
    additional_info=None,
):
    for img_slice_name, slice_path in slices.items():
        img_name = img_name_template.format(region=region, slice_name=img_slice_name)
        src = src_data_dir / src_dir_name / img_name
        dst = out_dir / out_name_template.format(
            region=region, slice_name=img_slice_name
        )
        if file_type == "mask":
            shutil.copy(src, dst)
        elif file_type == "expr":
            segmentation_channels = additional_info
            src = find_ome_tiff(src_data_dir)
            modify_and_save_img(src, dst, segmentation_channels)

        print("region:", region, "| src:", src, "| dst:", dst)


def collect_segm_masks(
    data_dir: Path, listing: Dict[int, Dict[str, str]], out_dir: Path
):
    out_name_template = "reg{region:03d}_{slice_name}_mask.ome.tiff"
    img_name_template = "reg{region:03d}_{slice_name}_mask.ome.tiff"
    dir_name_template = "region_{region:03d}"
    tasks = []
    for region, slices in listing.items():
        dir_name = dir_name_template.format(region=region)
        task = dask.delayed(copy_files)(
            "mask",
            data_dir,
            dir_name,
            img_name_template,
            out_dir,
            out_name_template,
            region,
            slices,
        )
        tasks.append(task)
    dask.compute(*tasks)


def collect_expr(
    data_dir: Path, listing: dict, out_dir: Path, segmentation_channels: Dict[str, str]
):
    out_name_template = "reg{region:03d}_{slice_name}_expr.ome.tiff"
    img_name_template = "{slice_name}.ome.tif"  # one f
    dir_name_template = "region_{region}"
    dir_name_template_3d = "region_{region:03d}"

    tasks = []
    for region, slices in listing.items():
        dir_name = dir_name_template.format(region=region) if (data_dir /
                    dir_name_template.format(region=region)).exists() else (dir_name_template_3d.format(region=region))
        task = dask.delayed(copy_files)(
            "expr",
            data_dir,
            dir_name,
            img_name_template,
            out_dir,
            out_name_template,
            region,
            slices,
            segmentation_channels,
        )
        tasks.append(task)
    dask.compute(*tasks)


def main(data_dir: Path, mask_dir: Path, pipeline_config_path: Path):
    data_dir = get_img_subdir(data_dir)
    pipeline_config = read_pipeline_config(pipeline_config_path)
    listing = pipeline_config["dataset_map_all_slices"]
    segmentation_channels = pipeline_config["segmentation_channels"]

    out_dir = Path("/output/pipeline_output")
    mask_out_dir = out_dir / "mask"
    expr_out_dir = out_dir / "expr"
    make_dir_if_not_exists(mask_out_dir)
    make_dir_if_not_exists(expr_out_dir)

    dask.config.set({"num_workers": 5, "scheduler": "processes"})
    print("\nCollecting segmentation masks")
    collect_segm_masks(mask_dir, listing, mask_out_dir)
    print("\nCollecting expressions")
    collect_expr(data_dir, listing, expr_out_dir, segmentation_channels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=Path, help="path to directory with images")
    parser.add_argument(
        "--mask_dir", type=Path, help="path to directory with segmentation masks"
    )
    parser.add_argument(
        "--pipeline_config", type=Path, help="path to region map file YAML"
    )
    args = parser.parse_args()

    main(args.data_dir, args.mask_dir, args.pipeline_config)
