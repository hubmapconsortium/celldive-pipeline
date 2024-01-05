import argparse
import logging
import re
import shutil
from os import walk
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import tifffile as tif
from aicsimageio import AICSImage
from ome_types import from_tiff
from ome_types.model import (
    AnnotationRef,
    Map,
    MapAnnotation,
    StructuredAnnotationList,
)

from utils import make_dir_if_not_exists, path_to_str, read_pipeline_config
from utils_ome import modify_initial_ome_meta

Image = np.ndarray
logging.basicConfig(level=logging.INFO, format="%(levelname)-7s - %(message)s")
logger = logging.getLogger(__name__)


def find_antibodies_meta(input_dir: Path) -> Optional[Path]:
    """
    Finds and returns the first metadata file for a HuBMAP data set.
    Does not check whether the dataset ID (32 hex characters) matches
    the directory name, nor whether there might be multiple metadata files.
    """
    metadata_filename_pattern = re.compile(r"^[0-9A-Za-z\-_]*antibodies\.tsv$")
    found_files = []
    for dirpath, dirnames, filenames in walk(input_dir):
        for filename in filenames:
            if metadata_filename_pattern.match(filename):
                found_files.append(Path(dirpath) / filename)

    if len(found_files) == 0:
        logger.warning("No antibody.tsv file found")
        antb_path = None
    else:
        antb_path = found_files[0]
    return antb_path


def map_antb_names(antb_df: pd.DataFrame):
    mapping = {
        channel_id: antibody_name
        for channel_id, antibody_name in zip(antb_df["channel_id"], antb_df["antibody_name"])
    }
    return mapping


def replace_channel_names(antb_df: pd.DataFrame, og_ch_names: List) -> List:
    mapping = map_antb_names(antb_df)
    updated_channel_names = [mapping.get(channel_id, channel_id) for channel_id in og_ch_names]
    return updated_channel_names


def generate_sa_ch_info(
    channel_name: str,
    channel_id: str,
    antb_df: pd.DataFrame,
) -> Optional[MapAnnotation]:
    try:
        antb_row = antb_df.loc[antb_df["antibody_name"] == channel_name]
    except KeyError:
        return None
    uniprot_id = antb_row["uniprot_accession_number"].iloc[0]
    rrid = antb_row["rr_id"].iloc[0]
    original_name = antb_row["channel_id"].iloc[0]
    channel_id_key = Map.M(k="Channel ID", value = channel_id)
    name_key = Map.M(k="Name", value=channel_name)
    og_name_key = Map.M(k="Original Name", value=original_name)
    uniprot_key = Map.M(k="UniprotID", value=uniprot_id)
    rrid_key = Map.M(k="RRID", value=rrid)
    ch_info = Map(ms=[channel_id_key, name_key, og_name_key, uniprot_key, rrid_key])
    annotation = MapAnnotation(value=ch_info)
    return annotation


def update_omexml(ome_tiff: Path, antb_df: pd.DataFrame) -> str:
    image = AICSImage(ome_tiff)
    original_channels = image.channel_names
    if original_channels == None:
        omexml = None
    else:
        updated_channels = replace_channel_names(antb_df, original_channels)
        omexml = from_tiff(ome_tiff)
        annotations = StructuredAnnotationList()
        for i, (channel_obj, channel_name, original_name) in enumerate(
            zip(omexml.images[0].pixels.channels, updated_channels, original_channels)
        ):
            channel_id = f"Channel:0:{i}"
            channel_obj.name = channel_name
            channel_obj.id = channel_id
            if original_name not in antb_df["channel_id"].values:
                continue
            ch_info = generate_sa_ch_info(channel_name, channel_id, antb_df)
            if ch_info is None:
                continue
            channel_obj.annotation_refs.append(AnnotationRef(id=ch_info.id))
            annotations.append(ch_info)
            omexml.structured_annotations = annotations
        omexml = omexml.to_xml()
        return omexml


def add_z_axis(img_stack: Image):
    stack_shape = img_stack.shape
    new_stack_shape = [stack_shape[0], 1, stack_shape[1], stack_shape[2]]
    return img_stack.reshape(new_stack_shape)


def modify_and_save_img(
    img_path: Path,
    out_path: Path,
    segmentation_channels: Dict[str, str],
    pixel_size_x: float,
    pixel_size_y: float,
    pixel_unit_x: str,
    pixel_unit_y: str,
    new_xml: Optional[str],
):
    with tif.TiffFile(path_to_str(img_path)) as TF:
        if new_xml == None:
            ome_meta = TF.ome_metadata
        else:
            ome_meta = new_xml
        img_stack = TF.series[0].asarray()
    new_img_stack = add_z_axis(img_stack)
    new_ome_meta = modify_initial_ome_meta(
        ome_meta, segmentation_channels, pixel_size_x, pixel_size_y, pixel_unit_x, pixel_unit_y
    )
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
        img_name = img_name_template.format(slice_name="1")
        src = src_data_dir / src_dir_name / img_name
        dst = out_dir / out_name_template.format(slice_name="1")
        if file_type == "mask":
            shutil.copy(src, dst)
        elif file_type == "expr":
            segmentation_channels = additional_info
            modify_and_save_img(src, dst, segmentation_channels)
        print("src:", src, "| dst:", dst)


def collect_segm_masks(data_dir: Path, out_dir: Path):
    for image_file in data_dir.glob("**/*.ome.tiff"):
        filename_base = image_file.name.split(".")[0]
        output_file = out_dir / image_file.name
        shutil.copy(image_file, output_file)


def collect_expr(
    data_dir: Path,
    listing: dict,
    out_dir: Path,
    segmentation_channels: Dict[str, str],
    pixel_size_x: float,
    pixel_size_y: float,
    pixel_unit_x: str,
    pixel_unit_y: str,
    antb_df: pd.DataFrame,
):
    for image_file in data_dir.glob("*.ome.tiff"):
        filename_base = image_file.name.split(".")[0]
        new_filename = f"{filename_base}_expr.ome.tiff"
        output_file = out_dir / new_filename
        new_xml = update_omexml(image_file, antb_df)

        modify_and_save_img(
            image_file,
            output_file,
            segmentation_channels,
            pixel_size_x,
            pixel_size_y,
            pixel_unit_x,
            pixel_unit_y,
            new_xml,
        )


def main(data_dir: Path, mask_dir: Path, pipeline_config_path: Path):
    pipeline_config = read_pipeline_config(pipeline_config_path)
    listing = pipeline_config["dataset_map_all_slices"]
    segmentation_channels = pipeline_config["segmentation_channels"]
    pixel_size_x = pipeline_config["pixel_size_x"]
    pixel_size_y = pipeline_config["pixel_size_y"]
    pixel_unit_x = pipeline_config["pixel_unit_x"]
    pixel_unit_y = pipeline_config["pixel_unit_y"]
    out_dir = Path("/output/pipeline_output")
    mask_out_dir = out_dir / "mask"
    expr_out_dir = out_dir / "expr"
    antb_path = find_antibodies_meta(data_dir)
    antb_info = pd.read_table(antb_path)
    updated_segmentation_channels = replace_channel_names(
        antb_info, [segmentation_channels["nucleus"], segmentation_channels["cell"]]
    )
    segmentation_channels["nucleus"] = updated_segmentation_channels[0]
    segmentation_channels["cell"] = updated_segmentation_channels[1]
    make_dir_if_not_exists(mask_out_dir)
    make_dir_if_not_exists(expr_out_dir)

    print("\nCollecting segmentation masks")
    collect_segm_masks(mask_dir, mask_out_dir)
    print("\nCollecting expressions")
    collect_expr(
        data_dir,
        listing,
        expr_out_dir,
        segmentation_channels,
        pixel_size_x,
        pixel_size_y,
        pixel_unit_x,
        pixel_unit_y,
        antb_info,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=Path, help="path to directory with images")
    parser.add_argument("--mask_dir", type=Path, help="path to directory with segmentation masks")
    parser.add_argument("--pipeline_config", type=Path, help="path to region map file YAML")
    args = parser.parse_args()

    main(args.data_dir, args.mask_dir, args.pipeline_config)
