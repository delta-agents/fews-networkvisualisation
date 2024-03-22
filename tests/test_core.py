from fewsvisualiser.core.dbconfigvis import DbConfigVis
from fewsvisualiser.analyse import delete_old_database
import logging
from pathlib import Path


def test_dbconfigvis():
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)

    dbpath = Path('tests/files/test.db3').resolve()
    delete_old_database(dbpath)

    db = DbConfigVis(dbpath, logger)    
    assert db is not None