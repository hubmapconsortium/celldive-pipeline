cwlVersion: v1.1
class: CommandLineTool
label: Prepare images for segmentation

requirements:
  DockerRequirement:
    dockerPull: hubmap/mibi-scripts:latest
    dockerOutputDirectory: "/output"

baseCommand: ["python", "/opt/prepare_segmentation_channels.py"]

inputs:
  data_dir:
    type: Directory
    inputBinding:
      prefix: "--data_dir"

  pipeline_config:
    type: File
    inputBinding:
      prefix: "--pipeline_config"


outputs:
  segmentation_channels:
    type: Directory
    outputBinding:
      glob: "/output/segmentation_channels/"
