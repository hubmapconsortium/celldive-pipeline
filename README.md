## CellDIVE pipeline

Prepares data and does 2D segmentation of CellDIVE using [deepcell](https://deepcell.readthedocs.io/en/latest/app-gallery/mesmer.html) method.  More information about DeepCell and the associated Mesmer algorithm can be found in the associated publication [here](https://www.nature.com/articles/s41592-019-0580-2).

This method was selected based on its performance in a number of metrics calculated without the use of a human segmented reference image in the process described in [this publication](https://www.molbiolcell.org/doi/full/10.1091/mbc.E22-08-0364)



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