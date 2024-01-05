cwlVersion: v1.1
class: CommandLineTool
label: Run segmentation

requirements:
  DockerRequirement:
    dockerPull: hubmap/segmentations:1.2.3
    dockerOutputDirectory: "/output"
  DockerGpuRequirement: {}
  NetworkAccess:
    networkAccess: true

baseCommand: ["python", "/opt/main.py"]

inputs:
  method:
    type: string
    inputBinding:
      prefix: "--method"

  dataset_dir:
    type: Directory
    inputBinding:
      prefix: "--dataset_dir"

  gpus:
    type: string
    inputBinding:
      prefix: "--gpus"

outputs:
  mask_dir:
    type: Directory
    outputBinding:
      glob: "/output"
