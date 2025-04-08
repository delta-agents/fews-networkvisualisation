from fewsvisualiser.core.dbconfigvis import DbConfigVis
from fewsvisualiser.analyse import delete_old_database
import fewsvisualiser
import logging
from pathlib import Path


def test_dbconfigvis():
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    dbpath = Path('tests/files/test.db3').resolve()
    delete_old_database(dbpath)

    db = DbConfigVis(dbpath, logger)    
    assert db is not None

def test_ix_119():
    # this is the root directory of your Delft-FEWS configuration
    dir_config_root = r"D:\Software\FEWS_BOS_Rijnland\FEWS\Config"

    # this is the sqlite database file that will be written upon analysing your config
    file_database = r"D:\Software\fews-networkvisualisation\db\FEWS_BOS_Rijnland.db3"
    
    # analyse your Delft-FEWS configuration files
    fewsvisualiser.analyse_config(dir_config_root, file_database)    