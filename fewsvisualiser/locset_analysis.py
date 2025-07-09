import fire
from pathlib import Path
from fewsvisualiser.core.locsetparser import Locset_parser
from fewsvisualiser.core.dblocset import DbCLocSet
from fewsvisualiser.core.helpers import setup_logging, delete_file


#=======================================================================================
# MAIN PROGRAM
def locset_analysis(croot, dbpath):
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

    db = DbCLocSet(dbpath, logger)
    db.create_tables(logger)

    Locset_parser.parse_locationsets(config_root, db, logger)

    #db.close(logger)
    #exit(0)
    #db.clear_tables(logger)

    db.close(logger)

if __name__ == "__main__":
    fire.Fire()