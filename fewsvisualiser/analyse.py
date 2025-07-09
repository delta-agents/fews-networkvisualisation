from pathlib import Path
from fewsvisualiser.core.dbconfigvis import DbConfigVis
from fewsvisualiser.core.fewsparsers import Workflows_parser, TimeseriesSetParser, Modins_parser, Endpoint_parsers, CoefficientSet_parser
from fewsvisualiser.core.helpers import setup_logging, delete_file


#=======================================================================================
# MAIN PROGRAM
def analyse_config(croot, dbpath):
    # Convert to Path objects
    dbpath_obj = Path(dbpath)
    
    # Extract the database name for the log file
    db_name = dbpath_obj.stem
    log_file = dbpath_obj.parent / f"{db_name}.log"
    
    # Ensure we start with clean files
    delete_file(log_file)  # Clean log file
    delete_file(dbpath)    # Clean database file
    
    # Setup logging
    global logger
    logger = setup_logging(__name__, str(log_file))
    
    logger.info(f"root: {croot}")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Starting with clean database: {dbpath}")
    config_root = Path(croot)

    db = DbConfigVis(dbpath, logger)
    db.create_tables(logger)

    # parsing workflow descriptors
    Workflows_parser.parse_workflow_descriptors(config_root, db, logger)
    # parsing workflow files
    Workflows_parser.loop_workflows(config_root, db, logger)

    #db.close(logger)
    #exit(0)
    #db.clear_tables(logger)

    # parsing TimeSteps
    TimeseriesSetParser.parse_timestep_id_file(config_root / "RegionConfigFiles/TimeSteps.xml", logger)
    # parsing filter files
    Endpoint_parsers.parse_endpoint(db, config_root / "RegionConfigFiles", 'filters', logger)
    # parsing displayGroups files
    Endpoint_parsers.parse_endpoint(db, config_root / "SystemConfigFiles", 'displayGroups', logger)
    # parsing gridDisplay files
    Endpoint_parsers.parse_endpoint(db, config_root / "DisplayConfigFiles", 'gridDisplay', logger)
    # parsing scadaDisplay (schematic displays) files
    Endpoint_parsers.parse_endpoint(db, config_root / "DisplayConfigFiles", 'scadaDisplay', logger)
    # parsing transformationCoefficientSets
    CoefficientSet_parser.parse(config_root / "CoefficientSetsFiles", logger)
    # parsing module instance files
    Modins_parser.parse_modins(db, config_root, logger)

    db.close(logger)