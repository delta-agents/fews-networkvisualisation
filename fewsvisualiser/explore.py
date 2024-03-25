import fire
import logging
from pathlib import Path
from fewsvisualiser.core.dbconfigvis import DbConfigVis


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

#=======================================================================================
# MAIN PROGRAM
def main(dbpath):
    try:
        db = DbConfigVis(dbpath, logger)

        trafo_desc = '"Kantelstuw.diffBenedenpeil"'
        trafo = db.general_query(f"SELECT * FROM trafos WHERE DESC = {trafo_desc}", logger)
        print(f"trafo: {trafo}")
        trafo_id = trafo[0][0]

        links = db.general_query(f"SELECT * FROM links WHERE trafo_id = {trafo_id}", logger)
        print(f"links: {links}")

        for link in links:
            tss_id = link[1]
            tss = db.general_query(f"SELECT * FROM ts_sets WHERE id = {tss_id}", logger)
            print(f"tss: {tss}")

        # waar wordt tss_id nog meer gebruikt als input?
        tss_id = 1679
        links = db.general_query(f"SELECT * FROM links WHERE tss_id = {tss_id} and inout = 'in'", logger)
        print(f"trafos met tss_id {tss_id}: {links}")

        mic_ids = set()
        for trafo_id, tss_id, inout in links:
            tss = db.general_query(f"SELECT * FROM ts_sets WHERE id = {tss_id}", logger)
            (desc, mic_id) = (db.general_query(f"SELECT desc, mic_id FROM trafos WHERE id = {trafo_id}", logger))[0]
            mic_ids.add(mic_id)
            print(f"trafos ({trafo_id} {tss_id} {inout} {desc}): {tss}")

        cs_ids = set()
        for micid in mic_ids:
            mic = db.general_query(f"SELECT * FROM modins_calls WHERE id = {micid}", logger)
            cs_ids.add(mic[0][1])
            print(f"mic: {mic}")

        for cs_id in cs_ids:
            cs = db.general_query(f"SELECT * FROM call_stacks WHERE id = {cs_id}", logger)
            print(f"call stack: {cs}")


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
   

if __name__ == "__main__":
   fire.Fire(main)