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

        dll_wfs_table = """CREATE TABLE wfs (
                id TEXT NOT NULL, 
                description TEXT NOT NULL, 
                filename TEXT NOT NULL, 
                CONSTRAINT PK_wfs PRIMARY KEY (id))"""
        cursor.execute(dll_wfs_table)
        logger.info("wfs table created")

        dll_wfd_props_table = """CREATE TABLE wfd_props (
                wf_id TEXT NOT NULL, 
                key TEXT NOT NULL, 
                value TEXT NOT NULL,
                FOREIGN KEY(wf_id) REFERENCES wfs(id),
                CONSTRAINT PK_wfd_props PRIMARY KEY (wf_id, key))"""
        cursor.execute(dll_wfd_props_table)
        logger.info("wfd_props table created")

        dll_props_sets_table = """CREATE TABLE props_sets (
                id INTEGER NOT NULL, 
                key TEXT NOT NULL, 
                value TEXT NOT NULL,
                CONSTRAINT PK_props_sets PRIMARY KEY (id, key))"""
        cursor.execute(dll_props_sets_table)
        logger.info("props_sets table created")

        dll_call_stacks_table = """CREATE TABLE call_stacks (
                id INTEGER NOT NULL, 
                ilevel INTEGER NOT NULL,
                wffn TEXT NOT NULL,
                CONSTRAINT PK_call_stacks PRIMARY KEY (id, ilevel))"""
        cursor.execute(dll_call_stacks_table)
        logger.info("call_stacks table created")

        dll_modins_calls_table = """CREATE TABLE modins_calls (
                id INTEGER NOT NULL,
                call_stack_id INTEGER NOT NULL,
                modins TEXT NOT NULL,
                props_set_id INTEGER,
                CONSTRAINT PK_modins_calls PRIMARY KEY (id, call_stack_id),
                FOREIGN KEY(props_set_id) REFERENCES props_set(id),
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
                                    CONSTRAINT PK_ts_sets PRIMARY KEY (id)
                                    )"""
        cursor.execute(dll_timeseries_sets_table)
        logger.info("ts_sets table created")

        dll_trafos_table = """CREATE TABLE trafos (
                                    id INTEGER NOT NULL,
                                    mic_id INTEGER NOT NULL,
                                    ord_nr INTEGER NOT NULL,
                                    desc TEXT NOT NULL,
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

        self.con.commit()
        logger.info("Database created")

    def get_call_stack_from_id(self, id, logger):
        try:
            cs = []
            cursor = self.con.cursor()
            for row in self.con.execute("SELECT wffn FROM call_stacks WHERE id =:id ORDER BY ilevel", {"id": id}).fetchall():
                cs.append[row[0]]
        except sqlite3.Error as error:
            logger.error(error)
        finally:
            cursor.close()
            return cs

    def get_tss(self, tss_id, logger):
        try:
            tss_row = self.con.execute("SELECT * FROM ts_sets WHERE id =:id", {"id": tss_id}).fetchone()
            return tss_row
        except sqlite3.Error as error:
            logger.error(error)

    def get_trafo_id(self, mic_id, ord_nr, desc, logger):
        try:
            cursor = self.con.cursor()
            # find trafo_id
            trafo_row = self.con.execute("SELECT id FROM trafos WHERE mic_id=:mic_id AND ord_nr=:ord_nr", {"mic_id": mic_id, "ord_nr": ord_nr}).fetchone()
            if trafo_row is None:
                trafo_row = self.con.execute("SELECT MAX(id) FROM trafos").fetchone()
                if trafo_row[0] is None:
                    trafo_id = 1
                else:
                    trafo_id = trafo_row[0] + 1
                insert_statement = """INSERT INTO 'trafos' ('id','mic_id','ord_nr','desc') VALUES (?, ?, ?, ?);"""
                cursor.execute(insert_statement, (trafo_id, mic_id, ord_nr, desc))
                self.con.commit()
            else:
                trafo_id = trafo_row[0]
        except sqlite3.Error as error:
            logger.error(error)
        finally:
            cursor.close()
            return trafo_id

    def add_inoutput(self, mic_id, ord_nr, desc, tss_id, direction, logger):
        trafo_id = self.get_trafo_id(mic_id, ord_nr, desc, logger)
        try:
            cursor = self.con.cursor()
            insert_statement = """INSERT INTO 'links' ('trafo_id','tss_id','inout') VALUES (?, ?, ?);"""
            cursor.execute(insert_statement, (trafo_id, tss_id, direction))
            self.con.commit()
        except sqlite3.IntegrityError as error:
            pass
        except sqlite3.Error as error:
            logger.warn(error)
        finally:
            cursor.close()

    def add_input(self, mic_id, ord_nr, desc, tss_id, logger):
        self.add_inoutput(mic_id, ord_nr, desc, tss_id, 'in', logger)

    def add_output(self, mic_id, ord_nr, desc, tss_id, logger):
        self.add_inoutput(mic_id, ord_nr, desc, tss_id, 'out', logger)

    def get_n_call_stacks(self):
        row = self.con.execute("SELECT count(*) FROM call_stacks").fetchone()
        return row[0]

    def add_call_stack_and_props(self, moduleConfigFileName, current_call_stack, current_properties_set, logger):
        try:
            cursor = self.con.cursor()
            # get ccs-id
            ccs_row = self.con.execute("SELECT MAX(id) FROM call_stacks").fetchone()
            if ccs_row[0] is None:
                ccs_id = 1
            else:
                ccs_id = int(ccs_row[0]) + 1
            # create a new ccs
            for ilevel in range(len(current_call_stack)):
                data = (ccs_id, ilevel+1, current_call_stack[ilevel])
                insert_statement = """INSERT INTO 'call_stacks' ('id','ilevel','wffn') VALUES (?, ?, ?);"""
                cursor.execute(insert_statement, data)

            # properties set can be empty
            if len(current_properties_set) > 0:
                # cps-id
                cps_row = self.con.execute("SELECT MAX(id) FROM props_sets").fetchone()
                if cps_row[0] is None:
                    cps_id = 1
                else:
                    cps_id = int(cps_row[0]) + 1
                # create a new cps
                for key, value in current_properties_set.items():
                    data = (cps_id, key, value)
                    try:
                        insert_statement = """INSERT INTO 'props_sets' ('id','key','value') VALUES (?, ?, ?);"""
                        logger.debug("INSERT INTO props_sets: {}".format(data))
                        cursor.execute(insert_statement, data)
                    except sqlite3.IntegrityError as error:
                        logger.error(error)
                        logger.warn("property overwritten: {}: {}; call stack: {}".format(key, value, current_call_stack))
                        update_statement = """UPDATE 'props_sets' SET value = ? WHERE id = ? AND key = ?"""
                        cursor.execute(update_statement, (value, cps_id, key))
            else:
                cps_id = None

            # modins_call_id
            mic_id_row = self.con.execute("SELECT MAX(id) FROM modins_calls").fetchone()
            if mic_id_row[0] is None:
                mic_id = 1
            else:
                mic_id = int(mic_id_row[0]) + 1
            data = (mic_id, ccs_id, moduleConfigFileName, cps_id)
            insert_statement = """INSERT INTO 'modins_calls' ('id', 'call_stack_id', 'modins', 'props_set_id') VALUES (?, ?, ?, ?);"""
            cursor.execute(insert_statement, data)
        finally:
            self.con.commit()
            cursor.close()
        
    def wfs_insert(self, wf_id, wf_desc, wf_fn):
        try:
            cursor = self.con.cursor()
            data = (wf_id, wf_desc, wf_fn)
            insert_statement = """INSERT INTO 'wfs' ('id','description','filename') VALUES (?, ?, ?);"""
            cursor.execute(insert_statement, data)
        finally:
            self.con.commit()
            cursor.close()

    def wfd_props_insert(self, wf_id, key, value):
        try:
            cursor = self.con.cursor()
            data = (wf_id, key, value)
            insert_statement = """INSERT INTO 'wfd_props' ('wf_id','key','value') VALUES (?, ?, ?);"""
            cursor.execute(insert_statement, data)
        finally:
            self.con.commit()
            cursor.close()

    def get_wfd_props(self, wf_id, logger):
        try:
            props = {}
            for row in self.con.execute("SELECT key, value FROM wfd_props WHERE wf_id =:wf_id", {"wf_id": wf_id}).fetchall():
                props[row[0]] = row[1]
            return props
        except sqlite3.Error as error:
            logger.error("Error while connecting to sqlite (get_wfd_props)", error)

    def get_workflow_filename(self, wf_id, logger):
        try:
            row = self.con.execute("SELECT filename FROM wfs WHERE id =:wf_id", {"wf_id": wf_id}).fetchone()
            if row is None:
                # it is possible to get here for nested workflows without their own description
                return wf_id
            else:
                return row[0]
        except sqlite3.Error as error:
            logger.error("Error get_workflow_filename: ", error)

    def list_wfs(self):
        return self.con.execute("SELECT id, filename FROM wfs").fetchall()

    def list_modins(self):
        return self.con.execute("SELECT id, modins, call_stack_id, props_set_id FROM modins_calls ORDER BY modins ASC").fetchall()

    def get_props_set(self, id, logger):
        try:
            props = {}
            for row in self.con.execute("SELECT key, value FROM props_sets WHERE id =:id", {"id": id}).fetchall():
                props[row[0]] = row[1]
            return props
        except sqlite3.Error as error:
            logger.error("Error get_props_set: ", error)

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
            insert_statement = """INSERT INTO 'ts_sets' ('id', 'modins', 'vtype', 'parid', 'qualifiers', 'tstype', 'timess') VALUES (?, ?, ?, ?, ?, ?, ?);"""
            cursor.execute(insert_statement, data)
            self.con.commit()
        except sqlite3.Error as error:
            logger.error("Error add_tts: ", error)
        finally:
            cursor.close()
            return tss_id

    def get_tss_id(self, tss, logger):
        try:
            select_statement = "SELECT id FROM ts_sets WHERE modins = ? AND vtype = ? AND parid = ? AND qualifiers = ? AND tstype = ? AND timess = ?"
            row = self.con.execute(select_statement, tss).fetchone()
            if row is None:
                tss_id = self.add_tts(tss, logger)
            else:
                tss_id = row[0]
        except sqlite3.Error as error:
            logger.error("Error get_tss_id: ", error)
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
        finally:
            cursor.close()

    def clear_tables(self, logger):
        try:
            cursor = self.con.cursor()
            cursor.execute("DELETE FROM endpoints")
            cursor.execute("DELETE FROM links")
            cursor.execute("DELETE FROM trafos")
            cursor.execute("DELETE FROM ts_sets")
        except sqlite3.Error as error:
            logger.error("Error clear_tables: ", error)
        finally:
            self.con.commit()
            cursor.close()

    def close(self, logger):
        try:
            self.con.close()
            logger.info("Db closed")
        except sqlite3.Error as error:
            logger.error("Error while closing to sqlite: ", error)

    def get_links_by_tss(self, tss_id, direction, logger):
        try:
            links = set()
            data = {"tss_id": tss_id, "inout": direction}
            for row in self.con.execute("SELECT * FROM links WHERE tss_id =:tss_id AND inout =:inout", data).fetchall():
                links.add(row)
            return links
        except sqlite3.Error as error:
            logger.error(error)

    def get_links_by_trafo(self, trafo_id, direction, logger):
        try:
            links = set()
            data = {"trafo_id": trafo_id, "inout": direction}
            for row in self.con.execute("SELECT * FROM links WHERE trafo_id =:trafo_id AND inout =:inout", data).fetchall():
                links.add(row)
            return links
        except sqlite3.Error as error:
            logger.error(error)

    def general_query(self, query, logger):
        try:
            return self.con.execute(query).fetchall()
        except sqlite3.Error as error:
            logger.error(error)