import sqlite3

class DbConfigVis:
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

        dll_props_sets_table = """CREATE TABLE props_sets (
                id INTEGER NOT NULL, 
                key TEXT NOT NULL, 
                value TEXT NOT NULL,
                CONSTRAINT PK_props_sets PRIMARY KEY (id, key))"""
        cursor.execute(dll_props_sets_table)
        logger.info("props_sets table created")

        dll_call_stacks_table = """CREATE TABLE call_stacks (
                id INTEGER NOT NULL,
                wf_id TEXT NOT NULL,
                desc TEXT,
                wffn TEXT NOT NULL,
                parent_id INTEGER,
                props_set_id INTEGER,
                CONSTRAINT PK_call_stacks PRIMARY KEY (id),
                FOREIGN KEY(props_set_id) REFERENCES props_sets(id),
                FOREIGN KEY(parent_id) REFERENCES call_stacks(id))"""
        cursor.execute(dll_call_stacks_table)
        logger.info("call_stacks table created")

        dll_modins_calls_table = """CREATE TABLE modins_calls (
                id INTEGER NOT NULL,
                call_stack_id INTEGER NOT NULL,
                modins TEXT NOT NULL,
                props_set_id INTEGER,
                CONSTRAINT PK_modins_calls PRIMARY KEY (id, call_stack_id),
                FOREIGN KEY(props_set_id) REFERENCES props_sets(id),
                FOREIGN KEY(call_stack_id) REFERENCES call_stacks(id))"""
        cursor.execute(dll_modins_calls_table)
        logger.info("modins_calls table created")

        dll_timeseries_sets_table = """CREATE TABLE ts_sets (
                                    id INTEGER NOT NULL,
                                    modins TEXT NOT NULL,
                                    vtype TEXT NOT NULL,
                                    parid TEXT NOT NULL,
                                    qualifiers TEXT,
                                    tstype TEXT NOT NULL,
                                    timess TEXT NOT NULL,
                                    aggregation TEXT,
                                    description TEXT,
                                    CONSTRAINT PK_ts_sets PRIMARY KEY (id)
                                    )"""
        cursor.execute(dll_timeseries_sets_table)
        logger.info("ts_sets table created")

        dll_trafos_table = """CREATE TABLE trafos (
                                    id INTEGER NOT NULL,
                                    mic_id INTEGER NOT NULL,
                                    ord_nr INTEGER NOT NULL,
                                    desc TEXT NOT NULL,
                                    config_file TEXT NOT NULL,
                                    CONSTRAINT PK_trafos PRIMARY KEY (id),
                                    UNIQUE(mic_id, ord_nr),
                                    FOREIGN KEY(mic_id) REFERENCES modins_calls(id)
                                    )"""
        cursor.execute(dll_trafos_table)
        logger.info("trafos table created")

        dll_links_table = """CREATE TABLE links (
                                    trafo_id INTEGER NOT NULL,
                                    tss_id INTEGER NOT NULL,
                                    inout TEXT,
                                    UNIQUE(trafo_id, tss_id, inout),
                                    FOREIGN KEY(trafo_id) REFERENCES trafos(id),
                                    FOREIGN KEY(tss_id) REFERENCES ts_sets(id)
                                    )"""
        cursor.execute(dll_links_table)
        logger.info("links table created")

        dll_endpoints_table = """CREATE TABLE endpoints (
                                    tss_id INTEGER NOT NULL,
                                    desc TEXT NOT NULL,
                                    CONSTRAINT PK_endpoints PRIMARY KEY (tss_id, desc),
                                    FOREIGN KEY(tss_id) REFERENCES ts_sets(id)
                                    )"""
        cursor.execute(dll_endpoints_table)
        logger.info("endpoints table created")

        dll_moduleinstances_table = """CREATE TABLE moduleinstances (
                                    modin_id TEXT NOT NULL,
                                    name TEXT NOT NULL,
                                    CONSTRAINT PK_moduleinstances PRIMARY KEY (modin_id))"""
        cursor.execute(dll_moduleinstances_table)
        logger.info("moduleinstances table created")

        self.con.commit()
        logger.info("Database created")

    def get_n_call_stacks(self):
        row = self.con.execute("SELECT count(*) FROM call_stacks").fetchone()
        return row[0]

    def get_n_modins_calls(self):
        row = self.con.execute("SELECT count(*) FROM modins_calls").fetchone()
        return row[0]

    def get_max_trafos_id(self) -> int:
        row = self.con.execute("SELECT MAX(id) FROM trafos").fetchone()
        return int(row[0]) if row[0] else 0

    def get_max_call_stacks_id(self) -> int:
        row = self.con.execute("SELECT MAX(id) FROM call_stacks").fetchone()
        return int(row[0]) if row[0] else 0

    def get_max_props_sets_id(self) -> int:
        row = self.con.execute("SELECT MAX(id) FROM props_sets").fetchone()
        return int(row[0]) if row[0] else 0

    def get_max_modins_calls_id(self) -> int:
        row = self.con.execute("SELECT MAX(id) FROM modins_calls").fetchone()
        return int(row[0]) if row[0] else 0

    def get_call_stack_from_wfid(self, wf_id, logger):
        try:
            cursor = self.con.cursor()
            cs = self.con.execute("SELECT id, desc, wffn, props_set_id FROM call_stacks WHERE wf_id =:wf_id", {"wf_id": wf_id}).fetchone()
        except sqlite3.Error as error:
            logger.error(error)
        finally:
            cursor.close()
            return cs

    def get_tss(self, tss_id, logger):
        try:
            return self.con.execute("SELECT * FROM ts_sets WHERE id =:id", {"id": tss_id}).fetchone()
        except sqlite3.Error as error:
            logger.error(error)
            raise

    def get_trafo_id(self, mic_id, ord_nr, desc, config_file, logger):
        try:
            cursor = self.con.cursor()
            # find trafo_id
            trafo_row = self.con.execute("SELECT id FROM trafos WHERE mic_id=:mic_id AND ord_nr=:ord_nr", {"mic_id": mic_id, "ord_nr": ord_nr}).fetchone()
            if trafo_row is None:
                trafo_id = self.get_max_trafos_id() + 1
                insert_statement = """INSERT INTO 'trafos' ('id','mic_id','ord_nr','desc', 'config_file') VALUES (?, ?, ?, ?, ?);"""
                cursor.execute(insert_statement, (trafo_id, mic_id, ord_nr, desc, config_file))
                self.con.commit()
            else:
                trafo_id = trafo_row[0]
        except sqlite3.Error as error:
            logger.error(error)
            raise
        finally:
            cursor.close()
            return trafo_id

    def add_inoutput(self, mic_id, ord_nr, desc, config_file, tss_id, direction, logger):
        trafo_id = self.get_trafo_id(mic_id, ord_nr, desc, config_file, logger)
        try:
            cursor = self.con.cursor()
            insert_statement = """INSERT INTO 'links' ('trafo_id','tss_id','inout') VALUES (?, ?, ?);"""
            cursor.execute(insert_statement, (trafo_id, tss_id, direction))
            self.con.commit()
        except sqlite3.IntegrityError as error:
            pass
        except sqlite3.Error as error:
            logger.warn(error)
            raise
        finally:
            cursor.close()

    def add_input(self, mic_id, ord_nr, desc, config_file, tss_id, logger):
        self.add_inoutput(mic_id, ord_nr, desc, config_file, tss_id, 'in', logger)

    def add_output(self, mic_id, ord_nr, desc, config_file, tss_id, logger):
        self.add_inoutput(mic_id, ord_nr, desc, config_file, tss_id, 'out', logger)

    def insert_props_set(self, properties_set, logger) -> int:
        if not properties_set:
            return None
        new_ps_id = self.get_max_props_sets_id() + 1
        try:
            cursor = self.con.cursor()
            for key, value in properties_set.items():
                data = (new_ps_id, key, value)
                try:
                    insert_statement = """INSERT INTO 'props_sets' ('id','key','value') VALUES (?, ?, ?);"""
                    logger.debug("INSERT INTO props_sets: {}".format(data))
                    cursor.execute(insert_statement, data)
                except sqlite3.IntegrityError as error:
                    logger.error(error)
                    logger.warn("property overwritten: {}: {}".format(key, value))
                    update_statement = """UPDATE 'props_sets' SET value = ? WHERE id = ? AND key = ?"""
                    cursor.execute(update_statement, (value, new_ps_id, key))
            self.con.commit()
        finally:
            cursor.close()
            return new_ps_id


    def add_call_stack(self, wfid, desc, wffn, parent, psid) -> int:
        try:
            cursor = self.con.cursor()
            ccs_id = self.get_max_call_stacks_id() + 1
            # create a new call stack
            data = (ccs_id, wfid, desc, wffn, parent, psid)
            insert_statement = """INSERT INTO 'call_stacks' ('id','wf_id','desc','wffn','parent_id','props_set_id') VALUES (?,?,?,?,?,?);"""
            cursor.execute(insert_statement, data)
            self.con.commit()
        finally:
            cursor.close()
            return ccs_id
        
        
    def add_modins_calls(self, modfn, csid, psid):
        try:
            cursor = self.con.cursor()
            mic_id = self.get_max_modins_calls_id() + 1
            data = (mic_id, csid, modfn, psid)
            insert_statement = """INSERT INTO 'modins_calls' ('id', 'call_stack_id', 'modins', 'props_set_id') VALUES (?, ?, ?, ?);"""
            cursor.execute(insert_statement, data)
            self.con.commit()
        finally:
            cursor.close()
        
    def wfs_insert(self, wf_id, wf_desc, wf_fn, cps_id):
        try:
            cursor = self.con.cursor()
            data = (wf_id, wf_desc, wf_fn, cps_id)
            insert_statement = """INSERT INTO 'wfs' ('id','description','filename', 'props_set_id') VALUES (?, ?, ?, ?);"""
            cursor.execute(insert_statement, data)
            self.con.commit()
        finally:
            cursor.close()

    def mid_insert(self, mi_id, mi_name):
        try:
            cursor = self.con.cursor()
            data = (mi_id, mi_name)
            insert_statement = """INSERT INTO 'moduleinstances' ('modin_id', 'name') VALUES (?, ?);"""
            cursor.execute(insert_statement, data)
            self.con.commit()
        finally:
            cursor.close()

    def list_wfs(self):
        return self.con.execute("SELECT id, wf_id, wffn, props_set_id FROM call_stacks").fetchall()

    def list_modins(self):
        return self.con.execute("SELECT id, modins, call_stack_id, props_set_id FROM modins_calls ORDER BY modins ASC").fetchall()

    def get_props_set(self, id, logger):
        try:
            props = {}
            [props.update({row[0]: row[1]}) for row in self.con.execute("SELECT key, value FROM props_sets WHERE id =:id", {"id": id}).fetchall()]
            return props
        except sqlite3.Error as error:
            logger.error("Error get_props_set: ", error)
            raise

    def add_tts(self, tss, logger):
        try:
            # tss_id
            tss_id_row = self.con.execute("SELECT MAX(id) FROM ts_sets").fetchone()
            if tss_id_row[0] is None:
                tss_id = 1
            else:
                tss_id = int(tss_id_row[0]) + 1

            cursor = self.con.cursor()
            data = (tss_id, ) + tss
            insert_statement = """INSERT INTO 'ts_sets' ('id', 'modins', 'vtype', 'parid', 'qualifiers', 'tstype', 'timess', 'aggregation', 'description') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);"""
            cursor.execute(insert_statement, data)
            self.con.commit()
        except sqlite3.Error as error:
            logger.error("Error add_tts: ", error)
        finally:
            cursor.close()
            return tss_id

    def get_tss_id(self, tss, logger):
        try:
            select_statement = "SELECT id, description FROM ts_sets WHERE modins = ? AND vtype = ? AND parid = ? AND qualifiers = ? AND tstype = ? AND timess = ? AND aggregation = ?"
            # the eighth elem is the description, which is optional
            desc_id = 7
            row = self.con.execute(select_statement, tss[0:desc_id]).fetchone()
            if row is None:
                tss_id = self.add_tts(tss, logger)
            else:
                tss_id = row[0]
                # append description if it exists
                if tss[7]:
                    if not tss[desc_id].lower() in row[1].lower():
                        # update the description
                        logger.info(f"Updating description for tss_id {tss_id}")
                        if row[1]:
                            new_description = row[1] + "; " + tss[desc_id].lower()
                        else:
                            new_description = tss[desc_id].lower()
                        update_statement = "UPDATE ts_sets SET description = ? WHERE id = ?"
                        self.con.execute(update_statement, (new_description, tss_id))
                        self.con.commit()
        except sqlite3.Error as error:
            logger.error("Error get_tss_id: ", error)
            raise
        finally:
            return tss_id

    def add_endpoint(self, tss_id, desc, logger):
        try:
            cursor = self.con.cursor()
            insert_statement = """INSERT INTO 'endpoints' ('tss_id','desc') VALUES (?, ?);"""
            cursor.execute(insert_statement, (tss_id, desc))
            self.con.commit()
        except sqlite3.IntegrityError as error:
            pass
        except sqlite3.Error as error:
            logger.error("Error add_endpoint: ", error)
            raise
        finally:
            cursor.close()

    def clear_tables(self, logger):
        try:
            cursor = self.con.cursor()
            cursor.execute("DELETE FROM endpoints")
            cursor.execute("DELETE FROM links")
            cursor.execute("DELETE FROM trafos")
            cursor.execute("DELETE FROM ts_sets")
            self.con.commit()
        except sqlite3.Error as error:
            logger.error("Error clear_tables: ", error)
            raise
        finally:
            cursor.close()

    def close(self, logger):
        try:
            self.con.close()
            logger.info("Db closed")
        except sqlite3.Error as error:
            logger.error("Error while closing to sqlite: ", error)
            raise

    def get_links_by_tss(self, tss_id, direction, logger):
        try:
            links = set()
            data = {"tss_id": tss_id, "inout": direction}
            [links.add(row) for row in self.con.execute("SELECT * FROM links WHERE tss_id =:tss_id AND inout =:inout", data).fetchall()]
            return links
        except sqlite3.Error as error:
            logger.error(error)
            raise

    def get_links_by_trafo(self, trafo_id, direction, logger):
        try:
            links = set()
            data = {"trafo_id": trafo_id, "inout": direction}
            [links.add(row) for row in self.con.execute("SELECT * FROM links WHERE trafo_id =:trafo_id AND inout =:inout", data).fetchall()]
            return links
        except sqlite3.Error as error:
            logger.error(error)
            raise

    def general_query(self, query, logger):
        try:
            return self.con.execute(query).fetchall()
        except sqlite3.Error as error:
            logger.error(error)