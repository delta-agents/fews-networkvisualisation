import logging
from pathlib import Path
from fewsvisualiser.core.dbconfigvis import DbConfigVis
from fewsvisualiser.core.helpers import setup_logging, delete_file


#=======================================================================================
# MAIN PROGRAM
def explore_config(dbpath):
    # Convert to Path objects
    dbpath_obj = Path(dbpath)
    
    # Extract the database name for the log file
    db_name = dbpath_obj.stem
    log_file = dbpath_obj.parent / f"{db_name}_explore.log"
    
    # Clean log file before starting
    delete_file(log_file)
    
    # Setup logging
    global logger
    logger = setup_logging(__name__, str(log_file))
    
    logger.info(f"Exploring database: {dbpath}")
    logger.info(f"Log file: {log_file}")
    
    try:
        db = DbConfigVis(dbpath, logger)
        
        # List some available transformations
        logger.info("Listing available transformations:")
        available_trafos = db.general_query("SELECT id, desc, mic_id FROM trafos LIMIT 10", logger)
        for trafo in available_trafos:
            logger.info(f"Transformation ID: {trafo[0]}, Description: {trafo[1]}, Module Instance ID: {trafo[2]}")
        
        # List some available time series sets
        logger.info("Listing available time series sets:")
        available_tss = db.general_query("SELECT id, modins, parid, qualifiers FROM ts_sets LIMIT 10", logger)
        for tss in available_tss:
            logger.info(f"TSS ID: {tss[0]}, Module Instance: {tss[1]}, Parameter ID: {tss[2]}, Qualifiers: {tss[3]}")
        
        # Now use a valid transformation from the ones we found (using the first one as an example)
        if available_trafos:
            trafo_desc = f'"{available_trafos[0][1]}"'
            logger.info(f"Using transformation description: {trafo_desc}")
        else:
            # Fallback to the existing value if no transformations found
            trafo_desc = '"Kantelstuw.diffBenedenpeil"'
            logger.info(f"No transformations found, using default: {trafo_desc}")
            
        trafo = db.general_query(f"SELECT * FROM trafos WHERE desc = {trafo_desc}", logger)
        logger.info(f"trafo: {trafo}")
        
        if not trafo:
            # If no transformation found with that description, list by ID instead
            logger.info("Transformation not found by description, trying direct ID lookup")
            trafo = db.general_query("SELECT * FROM trafos LIMIT 1", logger)
            if trafo:
                trafo_id = trafo[0][0]
                logger.info(f"Using transformation ID: {trafo_id}")
            else:
                logger.error("No transformations found in database")
                return
        else:
            trafo_id = trafo[0][0]

        links = db.general_query(f"SELECT * FROM links WHERE trafo_id = {trafo_id}", logger)
        logger.info(f"links: {links}")

        # Find a valid TSS ID from the links if possible
        valid_tss_id = None
        if links:
            valid_tss_id = links[0][1]
            logger.info(f"Using TSS ID from links: {valid_tss_id}")
        elif available_tss:
            valid_tss_id = available_tss[0][0]
            logger.info(f"Using TSS ID from available list: {valid_tss_id}")
        else:
            valid_tss_id = 1679  # Fallback to original value
            logger.info(f"No valid TSS ID found, using default: {valid_tss_id}")

        for link in links:
            tss_id = link[1]
            tss = db.general_query(f"SELECT * FROM ts_sets WHERE id = {tss_id}", logger)
            logger.info(f"tss: {tss}")

        # waar wordt tss_id nog meer gebruikt als input?
        tss_id = valid_tss_id
        links = db.general_query(f"SELECT * FROM links WHERE tss_id = {tss_id} and inout = 'in'", logger)
        logger.info(f"trafos met tss_id {tss_id}: {links}")

        mic_ids = set()
        for trafo_id, tss_id, inout in links:
            tss = db.general_query(f"SELECT * FROM ts_sets WHERE id = {tss_id}", logger)
            (desc, mic_id) = (db.general_query(f"SELECT desc, mic_id FROM trafos WHERE id = {trafo_id}", logger))[0]
            mic_ids.add(mic_id)
            logger.info(f"trafos ({trafo_id} {tss_id} {inout} {desc}): {tss}")

        cs_ids = set()
        for micid in mic_ids:
            mic = db.general_query(f"SELECT * FROM modins_calls WHERE id = {micid}", logger)
            cs_ids.add(mic[0][1])
            logger.info(f"mic: {mic}")

        for cs_id in cs_ids:
            cs = db.general_query(f"SELECT * FROM call_stacks WHERE id = {cs_id}", logger)
            logger.info(f"call stack: {cs}")


    finally:
        db.close(logger)

        # tss = db.get_tss(tss_id, logger)
        # logger.info(tss)
        # upstream_trafos = db.get_links_by_tss(tss_id, 'out', logger)

        # upstream_tsss = set()
        # for utr in upstream_trafos:
        #     i_tss_id = db.get_links_by_trafo(utr[0], 'in', logger)
        #     upstream_tsss = upstream_tsss.union(i_tss_id)
        # for itss in upstream_tsss:
        #     i_tss = db.get_tss(itss[0], logger)
        #     logger.info(i_tss)