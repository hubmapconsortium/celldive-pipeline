cwlVersion: v1.1
class: CommandLineTool
label: Collect segmentation masks and images for the final output

requirements:
  DockerRequirement:
    dockerPull: hubmap/mibi-scripts:latest
    dockerOutputDirectory: "/output"

baseCommand: ["python", "/opt/collect_output.py"]

inputs:
  data_dir:
    type: Directory
    inputBinding:
      prefix: "--data_dir"

  mask_dir:
    type: Directory
    inputBinding:
      prefix: "--mask_dir"

  pipeline_config:
    type: File
    inputBinding:
      prefix: "--pipeline_config"


outputs:
  pipeline_output:
    type: Directory
    outputBinding:
      glob: "/output/pipeline_output"
