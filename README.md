## CellDIVE pipeline

Prepares data and does 2D segmentation of CellDIVE images slice by slice using deepcell method.


### Usage example

`cwltool pipeline.cwl subm.yaml`

Requires `meta.yaml` with names of channels 
that will be used for segmentation of cell and nucleus compartments.


### The expected input directory structure:
```
HuBMAP_OME/
├── region_001
│     ├── S20030077_region_001.ome.tif
│     ├── S20030078_region_001.ome.tif
│     │              ...
│     └── S20030105_region_001.ome.tif
└── region_00N
      ├── S20030077_region_00N.ome.tif
      ├── S20030078_region_00N.ome.tif
      │             ...
      └── S20030105_region_00N.ome.tif
```

### The output structure:
```
pipeline_output/
├── expr
│   ├── reg001_S20030077_region_001_expr.ome.tiff
│   ├── reg002_S20030078_region_002_expr.ome.tiff
│   │                  ...
│   └── reg00N_S20030105_region_00N_expr.ome.tiff       
└── mask                                                                                  
    ├── reg001_S20030077_region_001_mask.ome.tiff
    ├── reg002_S20030078_region_002_mask.ome.tiff               
    │                  ...                   
    └── reg00N_S20030105_region_00N_mask.ome.tiff    
```