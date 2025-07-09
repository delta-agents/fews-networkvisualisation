import sqlite3

class DbCLocSet:
    def __init__(self, dbpath, logger):
        try:
            self.con = sqlite3.connect(database=dbpath)
            logger.info("Successfully connected to SQLite")
            version = sqlite3.sqlite_version_info
            logger.debug(f"SQLite Database Version is: {version}")
        except sqlite3.Error as error:
            logger.error("Error while connecting to SQLite", error)
            exit(1)

    def create_tables(self, logger):
        cursor = self.con.cursor()

        dll_locsets_table = """CREATE TABLE locsets (
                id TEXT NOT NULL, 
                name TEXT NOT NULL, 
                source TEXT NOT NULL,
                CONSTRAINT PK_locsets_id PRIMARY KEY (id))"""
        cursor.execute(dll_locsets_table)
        logger.info("locsets  table created")

        dll_locsets_relations_table = """CREATE TABLE locsets_relations (
                id TEXT NOT NULL, 
                parent_id TEXT,
                FOREIGN KEY(parent_id) REFERENCES locsets(id))"""
        cursor.execute(dll_locsets_relations_table)
        logger.info("locsets_relations table created")

        dll_attributes_table = """CREATE TABLE attributes (
                id TEXT NOT NULL,
                locset_id TEXT NOT NULL,
                name TEXT,
                source TEXT NOT NULL,
                FOREIGN KEY(locset_id) REFERENCES locsets(id))"""
        cursor.execute(dll_attributes_table)
        logger.info("attributes table created")
        self.con.commit()


    def insert_locset(self, locset, logger):
        cursor = self.con.cursor()
        try:
            cursor.execute("INSERT INTO locsets (id, name, source) VALUES (?, ?, ?)",
                           (locset['id'], locset['name'], locset.get('source', '')))
            self.con.commit()
            logger.info(f"Inserted locset: {locset['id']}")
        except sqlite3.Error as error:
            logger.error(f"Error inserting locset {locset['id']}: {error}")


    def insert_locset_relation(self, locset_id, parent_id, logger):
        cursor = self.con.cursor()
        try:
            cursor.execute("INSERT INTO locsets_relations (id, parent_id) VALUES (?, ?)",
                           (locset_id, parent_id))
            self.con.commit()
            logger.info(f"Inserted locset relation: {locset_id} -> {parent_id}")
        except sqlite3.Error as error:
            logger.error(f"Error inserting locset relation {locset_id} -> {parent_id}: {error}")


    def general_query(self, query, logger):
        try:
            return self.con.execute(query).fetchall()
        except sqlite3.Error as error:
            logger.error(error)


    def close(self, logger):
        try:
            self.con.close()
            logger.info("Db closed")
        except sqlite3.Error as error:
            logger.error("Error while closing to sqlite: ", error)
            raise
