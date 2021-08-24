cwlVersion: v1.1
class: CommandLineTool
label: Collect dataset info

hints:
  DockerRequirement:
    dockerPull: hubmap/celldive-scripts:1.1
    dockerOutputDirectory: "/output"

baseCommand: ["python", "/opt/collect_dataset_info.py"]

inputs:
  data_dir:
    type: Directory
    inputBinding:
      prefix: "--data_dir"

  meta_path:
    type: File
    inputBinding:
      prefix: "--meta_path"


outputs:
  pipeline_config:
    type: File
    outputBinding:
      glob: "/output/pipeline_config.yaml"
