import html
import unicodedata
from io import StringIO
from typing import Dict, Literal, Optional
from xml.etree import ElementTree as ET

from pint import Quantity, UnitRegistry

target_physical_size = "nm"
reg = UnitRegistry()


def strip_namespace(xmlstr: str):
    it = ET.iterparse(StringIO(xmlstr))
    for _, el in it:
        _, _, el.tag = el.tag.rpartition("}")
    root = it.root
    return root


def add_sa_segmentation_channels_info(omexml: ET.Element, nucleus_channel: str, cell_channel: str):
    """
    Will add this, to the root, after Image node
    <StructuredAnnotations>
    <XMLAnnotation ID="Annotation:0">
        <Value>
            <OriginalMetadata>
                <Key>SegmentationChannels</Key>
                <Value>
                    <Nucleus>DAPI-02</Nucleus>
                    <Cell>CD45</Cell>
                </Value>
            </OriginalMetadata>
        </Value>
    </XMLAnnotation>
    </StructuredAnnotations>
    """
    structured_annotation = ET.Element("StructuredAnnotations")
    annotation = ET.SubElement(structured_annotation, "XMLAnnotation", {"ID": "Annotation:0"})
    annotation_value = ET.SubElement(annotation, "Value")
    original_metadata = ET.SubElement(annotation_value, "OriginalMetadata")
    segmentation_channels_key = ET.SubElement(
        original_metadata, "Key"
    ).text = "SegmentationChannels"
    segmentation_channels_value = ET.SubElement(original_metadata, "Value")
    ET.SubElement(segmentation_channels_value, "Nucleus").text = nucleus_channel
    ET.SubElement(segmentation_channels_value, "Cell").text = cell_channel
    omexml.append(structured_annotation)


def physical_size_to_quantity(
    px_node: ET.Element,
    dimension: Literal["X", "Y"],
) -> Optional[Quantity]:
    unit_str = px_node.get(f"PhysicalSize{dimension}Unit", None)
    if unit_str is None:
        print("Could not find physical unit in OMEXML for dimension", dimension)
        return None

    size_str = px_node.get(f"PhysicalSize{dimension}", None)
    if size_str is None:
        print("Could not find physical unit in OMEXML for dimension", dimension)
        return None

    unit_normalized = unicodedata.normalize("NFKC", html.unescape(unit_str))
    size = float(size_str) * reg[unit_normalized]
    return size


def convert_size_to_nm(px_node: ET.Element):
    for dimension in "XY":
        size = physical_size_to_quantity(px_node, dimension)
        if size is not None:
            size_converted = size.to(target_physical_size)
            px_node.set(f"PhysicalSize{dimension}Unit", target_physical_size)
            px_node.set(f"PhysicalSize{dimension}", str(size_converted.magnitude))


def remove_tiffdata(px_node: ET.Element):
    for td in px_node.findall("TiffData"):
        px_node.remove(td)


def generate_and_add_new_tiffdata(px_node: ET.Element):
    num_channels = int(px_node.get("SizeC"))
    num_z = int(px_node.get("SizeZ"))
    ifd = 0
    for c in range(0, num_channels):
        for z in range(0, num_z):
            td = ET.Element(
                "TiffData",
                {
                    "FirstT": "0",
                    "FirstC": str(c),
                    "FirstZ": str(z),
                    "IFD": str(ifd),
                    "PlaneCount": "1",
                },
            )
            px_node.append(td)
            ifd += 1


def modify_initial_ome_meta(
    xml_str: str,
    segmentation_channels: Dict[str, str],
    pixel_size_x: float,
    pixel_size_y: float,
    pixel_unit_x: str,
    pixel_unit_y: str,
):
    new_dim_order = "XYZCT"
    ome_xml: ET.Element = strip_namespace(xml_str)
    ome_xml.set("xmlns", "http://www.openmicroscopy.org/Schemas/OME/2016-06")
    px_node = ome_xml.find("Image").find("Pixels")
    px_node.set("DimensionOrder", new_dim_order)
    px_node.set("PhysicalSizeX", str(pixel_size_x))
    px_node.set("PhysicalSizeY", str(pixel_size_y))
    px_node.set("PhysicalSizeXUnit", pixel_unit_x)
    px_node.set("PhysicalSizeYUnit", pixel_unit_y)
    convert_size_to_nm(px_node)
    remove_tiffdata(px_node)
    generate_and_add_new_tiffdata(px_node)
    add_sa_segmentation_channels_info(
        ome_xml, segmentation_channels["nucleus"], segmentation_channels["cell"]
    )
    new_xml_str = ET.tostring(ome_xml).decode("ascii")
    res = '<?xml version="1.0" encoding="utf-8"?>\n' + new_xml_str
    return res
