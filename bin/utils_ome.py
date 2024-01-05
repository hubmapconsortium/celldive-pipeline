import unicodedata
from io import StringIO
from typing import Dict
from xml.etree import ElementTree as ET


def strip_namespace(xmlstr: str):
    it = ET.iterparse(StringIO(xmlstr))
    for _, el in it:
        _, _, el.tag = el.tag.rpartition("}")
    root = it.root
    return root


def add_sa_segmentation_channels_info(
    omexml: ET.Element, nucleus_channel: str, cell_channel: str
):
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
    annotation = ET.SubElement(
        structured_annotation, "XMLAnnotation", {"ID": "Annotation:0"}
    )
    annotation_value = ET.SubElement(annotation, "Value")
    original_metadata = ET.SubElement(annotation_value, "OriginalMetadata")
    segmentation_channels_key = ET.SubElement(
        original_metadata, "Key"
    ).text = "SegmentationChannels"
    segmentation_channels_value = ET.SubElement(original_metadata, "Value")
    ET.SubElement(segmentation_channels_value, "Nucleus").text = nucleus_channel
    ET.SubElement(segmentation_channels_value, "Cell").text = cell_channel
    omexml.append(structured_annotation)


def convert_um_to_nm(px_node: ET.Element):
    unit_x = px_node.get("PhysicalSizeXUnit", None)
    unit_y = px_node.get("PhysicalSizeYUnit", None)
    size_x = px_node.get("PhysicalSizeX", None)
    size_y = px_node.get("PhysicalSizeY", None)
    um = unicodedata.normalize("NFKC", "μm")
    if size_x is None or size_y is None:
        print("Could not find physical pixel size in OMEXML")
        return
    if unit_x is None or unit_y is None:
        print("Could not find physical unit in OMEXML")
        return
    else:
        if unicodedata.normalize("NFKC", unit_x) == um or unit_x == "&#181;m":
            px_node.set("PhysicalSizeXUnit", "nm")
            px_node.set("PhysicalSizeX", str(float(size_x) * 1000))
        if unicodedata.normalize("NFKC", unit_y) == um or unit_y == "&#181;m":
            px_node.set("PhysicalSizeYUnit", "nm")
            px_node.set("PhysicalSizeY", str(float(size_y) * 1000))


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


def modify_initial_ome_meta(xml_str: str, segmentation_channels: Dict[str, str]):
    new_dim_order = "XYZCT"
    ome_xml: ET.Element = strip_namespace(xml_str)
    ome_xml.set("xmlns", "http://www.openmicroscopy.org/Schemas/OME/2016-06")
    px_node = ome_xml.find("Image").find("Pixels")
    px_node.set("DimensionOrder", new_dim_order)
    convert_um_to_nm(px_node)
    remove_tiffdata(px_node)
    generate_and_add_new_tiffdata(px_node)

    ome_xml.remove(ome_xml.find("StructuredAnnotations"))
    add_sa_segmentation_channels_info(
        ome_xml, segmentation_channels["nucleus"], segmentation_channels["cell"]
    )
    new_xml_str = ET.tostring(ome_xml).decode("ascii")
    res = '<?xml version="1.0" encoding="utf-8"?>\n' + new_xml_str
    return res
