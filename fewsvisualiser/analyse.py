import logging
from pathlib import Path
from fewsvisualiser.core.dbconfigvis import DbConfigVis
from fewsvisualiser.core.fewsparsers import Workflows_parser, TimeseriesSetParser, Modins_parser, Endpoint_parsers, CoefficientSet_parser


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

def delete_old_database(dbpath):
    p = Path(dbpath)
    if p.exists():
        p.unlink()
        logger.info("Existing db deleted")

#=======================================================================================
# MAIN PROGRAM
def analyse_config(croot, dbpath):
    logger.info(f"root: {croot}")
    config_root = Path(croot)

    delete_old_database(dbpath)

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