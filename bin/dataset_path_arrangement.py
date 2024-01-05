import re
from pathlib import Path
from typing import Dict, List


def alpha_num_order(string: str) -> str:
    """Returns all numbers on 5 digits to let sort the string with numeric order.
    Ex: alpha_num_order("a6b12.125")  ==> "a00006b00012.00125"
    """
    return "".join(
        [format(int(x), "05d") if x.isdigit() else x for x in re.split(r"(\d+)", string)]
    )


def sort_dict(item: dict) -> dict:
    return {k: sort_dict(v) if isinstance(v, dict) else v for k, v in sorted(item.items())}


def get_img_listing(in_dir: Path) -> List[Path]:
    allowed_extensions = (".tif", ".tiff")
    listing = list(in_dir.iterdir())
    img_listing = [f for f in listing if f.suffix in allowed_extensions]
    img_listing = sorted(img_listing, key=lambda x: alpha_num_order(x.name))
    return img_listing


def extract_digits_from_string(string: str) -> List[int]:
    digits = [
        int(x) for x in re.split(r"(\d+)", string) if x.isdigit()
    ]  # '1_00001_Z02_CH3' -> '1', '00001', '02', '3' -> [1,1,2,3]
    return digits


def extract_channel_name(file_name: str) -> str:
    return re.sub("(\.ome)?\.ti(ff|f)", "", file_name, flags=re.IGNORECASE)


def get_channel_listing(dataset_dir: Path, listing: List[Path]) -> Dict[str, Path]:
    arranged_listing = dict()
    for file_path in listing:
        channel_name = extract_channel_name(file_path.name)
        # returns relative path to dataset_dir
        arranged_listing[channel_name] = file_path.relative_to(dataset_dir)
    return arranged_listing


def name_contains(pattern, name) -> bool:
    res = re.search(pattern, name, re.IGNORECASE) is not None
    return res


def get_region_listing(dataset_dir: Path) -> Dict[int, Path]:
    regions_dirs = [p for p in list(dataset_dir.iterdir()) if p.is_dir()]
    regions_dirs = sorted(regions_dirs, key=lambda path: alpha_num_order(path.name))
    arranged_listing = dict()
    for region_dir in regions_dirs:
        # dir names expected to be Region_001, Region_002 ...
        if name_contains("Region", region_dir.name):
            digits = extract_digits_from_string(region_dir.name)
            region = digits[0]
            arranged_listing[region] = region_dir
    return arranged_listing


def create_listing_for_each_region(dataset_dir: Path) -> Dict[int, Dict[str, Path]]:
    # output of this function contains local paths to regions and channels relative to dataset_dir
    dataset_dir = dataset_dir.absolute()
    region_dict = get_region_listing(dataset_dir)
    arranged_listing = dict()
    for region, dir_path in region_dict.items():
        this_region_img_listing = get_img_listing(dataset_dir / dir_path)
        arranged_listing[region] = get_channel_listing(dataset_dir, this_region_img_listing)
    arranged_listing = sort_dict(arranged_listing)
    return arranged_listing
