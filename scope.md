# Workplan

1. final goal: use an intelligent language model to talk with Delft-FEWS configuration and data. No need to implement any code related to this.
2. understand the current repository. It is about reading configuration used for delft-fews software. 
3. It ingest the structures of this configuration into a sqlite database.
4. It defines functions to read this structure for this sqlite database, such as the following two diagram with a focus on timeserieset or transformations:

**Focus on TimeSeriesSet**
```mermaid
graph LR
  subgraph flow [ ]
    tf_out["`
    **Transformation(s) Out**
    _(select trafo_id from links where tss_id = 236 and inout = 'out')_
    `"]
    ts_set["`
    **Timeseries Set**
    _ts_sets (id = 236)_
    -
    moduleInstanceId: WerkFilter
    valueType: scalar
    parameterId: H.G.0
    timeStep unit: nonequidistant
    `"]
    tf_in["`
    **Transformation(s) In**
    _(select trafo_id from links where tss_id = 236 and inout = 'in')_    
    `"]
    tf_out --> ts_set --> tf_in
  end
  subgraph final [ ]
    endpoint["`
    Endpoint
    _(select * from endpoints where tss_id = 236)_
    `"]
    ts_set --> endpoint
  end
```

**Focus on transformations**
```mermaid
graph LR
  subgraph flow [ ]
    ts_in["`
    **TimeseriesSet(s)**
    _(select tss_id from links where trafo_id = 785 and inout = 'in')_
    `"]
    subgraph modin ["`
    ModIns_Call (id = 1283)
    _(select * from modins_calls where id = 1283)_
    `"]
        tf["`
        **Transformation**
        _Trafos (select * from trafos where id = 785)_
        -
        transformation id: CopySet.$LOCSET$.$PAR$
        CopySet.OW_WS.H.G.0
        `"]
    end
    ts_out["`
    **TimeseriesSet(s)**
    _(select tss_id from links where trafo_id = 785 and inout = ‘out')_    
    `"]
    ts_in --> tf --> ts_out
  end
callstack["`
Call stack (id=50)
_(select * from call_stacks where id = 50)_
wf_MetingenFilterCopyTest
(workflowFilename, PropertiesSet)
`"]
callstack --> modin
```

Can you create a technical document explaining this repository.