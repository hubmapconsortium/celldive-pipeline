import argparse
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import dask
import numpy as np
import tifffile as tif

from utils import make_dir_if_not_exists, path_to_str, read_pipeline_config
from utils_ome import modify_initial_ome_meta
from aicsimageio import AICSImage
from aicsimageio.writers.ome_tiff_writer import OmeTiffWriter
from ome_types.model import MapAnnotation, StructuredAnnotationList, Map, AnnotationRef, OME
from antibodies_tsv_util import antibodies_tsv_util as ab_tools
import pandas as pd

Image = np.ndarray


def collect_expressions_extract_channels(extractFile: Path) -> List[str]:
    """
    Given a TIFF file path, read file with TiffFile to get Labels attribute from
    ImageJ metadata. Return a list of the channel names in the same order as they
    appear in the ImageJ metadata.
    We need to do this to get the channel names in the correct order, and the
    ImageJ "Labels" attribute isn't picked up by AICSImageIO.
    """

    with tif.TiffFile(str(extractFile.absolute())) as TF:
        ij_meta = TF.imagej_metadata
    numChannels = int(ij_meta["channels"])
    channelList = ij_meta["Labels"][0:numChannels]
    return channelList


def map_antb_names(antb_df: pd.DataFrame):
    mapping = {
        channel_id: antibody_name
        for channel_id, antibody_name in zip(antb_df["channel_id"], antb_df["channel_name"])
    }
    return mapping


def replace_channel_names(antb_df: pd.DataFrame, og_ch_names: List) -> List:
    mapping = map_antb_names(antb_df)
    updated_channel_names = [mapping.get(channel_id, channel_id) for channel_id in og_ch_names]
    return updated_channel_names


def generate_sa_ch_info(
    channel_name: str,
    antb_df: pd.DataFrame,
) -> Optional[MapAnnotation]:
    try:
        antb_row = antb_df.loc[antb_df['antibody_name'] == channel_name]
    except KeyError:
        return None
    uniprot_id = antb_row["uniprot_accession_number"]
    rrid = antb_row["rr_id"]
    original_name = antb_row["channel_id"]
    name_key = Map.M(k="Name", value=channel_name)
    og_name_key = Map.M(k="Original Name", value=original_name)
    uniprot_key = Map.M(k="UniprotID", value=uniprot_id)
    rrid_key = Map.M(k="RRID", value=rrid)
    ch_info = Map(ms=[name_key, og_name_key, uniprot_key, rrid_key])
    annotation = MapAnnotation(value=ch_info)
    return annotation


def update_omexml(ome_tiff: Path, antb_df: pd.DataFrame) -> OME():
    original_channels = collect_expressions_extract_channels(ome_tiff)
    updated_channels = replace_channel_names(antb_df, original_channels)
    image = AICSImage(ome_tiff)
    omexml = OmeTiffWriter.build_ome(
        data_shapes=[(image.dims.T, image.dims.C, image.dims.Z, image.dims.Y, image.dims.X)],
        data_types=[image.dtype],
        dimension_order=["TCZYX"],
        channel_names=[updated_channels],
        image_name=[ome_tiff.name],
        physical_pixel_sizes=[image.physical_pixel_sizes],
    )
    annotations = StructuredAnnotationList()
    for i, (channel_obj, channel_name, original_name) in enumerate(
        zip(
            omexml.images[0].pixels.channels,
            updated_channels,
            original_channels
        )
    ):
        channel_id = f"Channel:0:{i}"
        channel_obj.name = channel_name
        channel_obj.id = channel_id
        if antb_df is None:
            continue
        if original_name==channel_name:
            continue
        ch_info = generate_sa_ch_info(channel_name, antb_df)
        if ch_info is None:
            continue
        channel_obj.annotation_refs.append(AnnotationRef(id=ch_info.id))
        annotations.append(ch_info)
        omexml.structured_annotations = annotations
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
    antb_df: pd.DataFrame,
):
    with tif.TiffFile(path_to_str(img_path)) as TF:
        ome_meta = TF.ome_metadata
        img_stack = TF.series[0].asarray()
    new_img_stack = add_z_axis(img_stack)
    new_ome_meta = modify_initial_ome_meta(
        ome_meta, segmentation_channels, pixel_size_x, pixel_size_y, pixel_unit_x, pixel_unit_y
    )
    with tif.TiffWriter(path_to_str(out_path), bigtiff=True) as TW:
        TW.save(
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
    antb_df: pd.DataFrame,
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
        modify_and_save_img(
            image_file,
            output_file,
            segmentation_channels,
            pixel_size_x,
            pixel_size_y,
            pixel_unit_x,
            pixel_unit_y,
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
    antb_path = ab_tools.find_antibodies_meta(data_dir)
    antb_info = pd.read_table(antb_path)
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
