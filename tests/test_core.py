from fewsvisualiser.core.dbconfigvis import DbConfigVis
from fewsvisualiser.analyse import delete_old_database
import logging
from pathlib import Path
import pytest


def test_dbconfigvis():
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    dbpath = Path('files/test.db3').resolve()
    delete_old_database(dbpath)

    # OperationalError('unable to open database file')
    with pytest.raises(Exception):
        db = DbConfigVis(dbpath, logger)    

    # assert db is not None
    assert True