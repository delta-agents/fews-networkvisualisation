import fire
import logging
from pathlib import Path
from DbConfigVis import DbConfigVis


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

#=======================================================================================
# MAIN PROGRAM
def main(dbpath, tss_id):
    logger.info(f"root: {tss_id}")

    db = DbConfigVis(dbpath, logger)

    tss = db.get_tss(tss_id, logger)
    logger.info(tss)
    upstream_trafos = db.get_links_by_tss(tss_id, 'out', logger)

    upstream_tsss = set()
    for utr in upstream_trafos:
        i_tss_id = db.get_links_by_trafo(utr[0], 'in', logger)
        upstream_tsss = upstream_tsss.union(i_tss_id)
    for itss in upstream_tsss:
        i_tss = db.get_tss(itss[0], logger)
        logger.info(i_tss)



    db.close(logger)

if __name__ == "__main__":
   fire.Fire(main)