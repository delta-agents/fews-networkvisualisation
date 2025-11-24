import xml.etree.ElementTree as ET
from fewsvisualiser.core.helpers import Helpers
import copy
import csv


ns = {'fews': 'http://www.wldelft.nl/fews'}
# user simple symbols
# N.B. some of these html symbols are interpreted by python: therefore &gt; and >
symbols_delimiters = ['+','-','/','*','^','&gt;','>','&lt;','<','&gt;=','&lt;=','&amp;&amp;','&&','=','!','(',')','||',',']
symbols_strings = ['isMissing','if','or','and','sin','cos','tan','asin','acos','atan','sinh','cosh', \
                   'tanh','asinh','acosh','atanh','log','ln','exp','sqrt','abs','pow','max','min', 'pi', 'NaN', '"NaN"', 'PREVIOUS_OUTPUT_VALUE', '']
ignored_modules = { r'{http://www.wldelft.nl/fews}reportExport', \
                    r'{http://www.wldelft.nl/fews}secondaryValidation', \
                    r'{http://www.wldelft.nl/fews}importAmalgamate',  \
                    r'{http://www.wldelft.nl/fews}configUpdateModule', \
                    r'{http://www.wldelft.nl/fews}forecastLengthEstimator', \
                    r'{http://www.wldelft.nl/fews}contentUpdateChecker'}

tsid_map = {}
coefficientSets = {}

class TimeseriesSetParser:
    @staticmethod
    def parse_timestep_id_file(tsid_path, logger):
        logger.debug(f"Parsing {tsid_path}")
        tsid_root = ET.parse(tsid_path).getroot()
        for ts in tsid_root.findall('fews:timeStep', ns):
            timestep = {'multiplier': "", 'unit': "", 'timeZone': ""}
            [timestep.update({key: value}) for key, value in ts.attrib.items()]
            timestepstring = "{}{}{}".format(timestep['multiplier'], timestep['unit'], timestep['timeZone'])
            if 'monthDays' in timestep.keys():
                timestepstring = "{}{}".format(timestepstring, timestep['monthDays'])
            tsid_map[timestep['id']] = timestepstring
        
        for ymw_ts in ("yearlyTimeStep", "monthlyTimeStep", "weeklyTimeStep"):
            for ts in tsid_root.findall(f"fews:{ymw_ts}", ns):
                ts_id = ts.get('id')
                timestepstring = "{}_{}".format(ymw_ts, ts_id)
                tsid_map[ts_id] = timestepstring

    @staticmethod
    def parse_tss(root_tss, props, mic_id = ""):
        """Parse a timeseries set XML element.
        
        Args:
            root_tss: The XML element containing the timeSeriesSet
            props: Properties dictionary for variable substitution
            mic_id: Optional module instance call ID
            
        Returns:
            A tuple containing timeseries set information
            
        Raises:
            ValueError: If required elements are missing from the XML
        """
        if root_tss is None:
            raise ValueError("Cannot parse timeSeriesSet: XML element is None")
            
        # Find and validate required elements
        mod_ins_elem = root_tss.find('fews:moduleInstanceId', ns)
        if mod_ins_elem is None or mod_ins_elem.text is None:
            raise ValueError("Missing moduleInstanceId in timeSeriesSet")
        moduleInstanceId = Helpers.solve_props(mod_ins_elem.text, props)
        
        val_type_elem = root_tss.find('fews:valueType', ns)
        if val_type_elem is None or val_type_elem.text is None:
            raise ValueError("Missing valueType in timeSeriesSet")
        valueType = Helpers.solve_props(val_type_elem.text, props)
        
        param_id_elem = root_tss.find('fews:parameterId', ns)
        if param_id_elem is None or param_id_elem.text is None:
            raise ValueError("Missing parameterId in timeSeriesSet")
        parameterId = Helpers.solve_props(param_id_elem.text, props)
        
        ts_type_elem = root_tss.find('fews:timeSeriesType', ns)
        if ts_type_elem is None or ts_type_elem.text is None:
            raise ValueError("Missing timeSeriesType in timeSeriesSet")
        timeSeriesType = Helpers.solve_props(ts_type_elem.text, props)
        # temporary series are only the same in case they share the same call stack
        if timeSeriesType == "temporary": timeSeriesType = f"tmp_{mic_id}" 

        # multiple qualifiers are possible
        q_list = []
        qualifiers = ""
        [q_list.append(Helpers.solve_props(q.text, props)) for q in root_tss.findall('fews:qualifierId', ns) if q.text is not None]
        for q in sorted(q_list):
            qualifiers = qualifiers + (('/' + q) if len(qualifiers) > 0 else q)

        timestep_elem = root_tss.find('fews:timeStep', ns)
        if timestep_elem is None:
            raise ValueError("Missing timeStep in timeSeriesSet")
            
        timestep = {'id': "", 'multiplier': "", 'unit': "", 'timeZone': ""}
        [timestep.update({key: Helpers.solve_props(value, props)}) for key, value in timestep_elem.items()]
        if timestep.get('id'):
            timestepstring = tsid_map[timestep['id']]
        else:
            timestepstring = "{}{}{}".format(timestep['multiplier'], timestep['unit'], timestep['timeZone'])

        # aggregationPeriod is not mandatory, but if it exists, it should be parsed
        aggregationPeriod_elem = root_tss.find('fews:aggregationPeriod', ns)
        if aggregationPeriod_elem is not None:
            aggregationPeriod = {'unit': "", 'start': "", 'end': ""}
            [aggregationPeriod.update({key: value}) for key, value in aggregationPeriod_elem.items()]
            aggregationString = "{}_{}_{}".format(aggregationPeriod['unit'], aggregationPeriod['start'], aggregationPeriod['end'])
        else:
            aggregationString = ""

        # optional element description can be different at different places in the config for the same tss
        description_elem = root_tss.find('fews:description', ns)
        if description_elem is not None:
            description = Helpers.solve_props(description_elem.text, props).lower().strip()
        else:
            description = ""

        return (moduleInstanceId, valueType, parameterId, qualifiers, timeSeriesType, timestepstring, aggregationString, description)

class ModuleInstanceDescriptorParser:
    @staticmethod
    def parse_moduleinstances_file(db, config_root, logger):
        mid_path = config_root / "RegionConfigFiles/ModuleInstanceDescriptors.xml" 
        logger.debug(f"Parsing {mid_path}")
        mid_root = ET.parse(mid_path).getroot()

        mid_csv = mid_root.find('fews:moduleInstanceDescriptorsCsvFile', ns)
        if mid_csv is None:
            for mid in mid_root.findall('fews:moduleInstanceDescriptor', ns):
                mi_id = mid.attrib["id"]
                try:
                    mi_name = mid.attrib["name"]
                except KeyError:
                    mi_name = mi_id

                db.mid_insert(mi_id, mi_name)
                logger.debug("parse_moduleinstances_file: adding moduleInstanceDescriptor {mi_id}")
        else:
            logger.debug("Parsing moduleInstanceDescriptorsCsvFile")
            moduleInstanceDescriptorsCsvFile = mid_csv.find('fews:file', ns).text
            id_column = mid_csv.find('fews:id', ns).text

            csv_path = config_root / "MapLayerFiles" / moduleInstanceDescriptorsCsvFile
            if csv_path.suffix != '.csv':
                csv_path = config_root / "MapLayerFiles" / moduleInstanceDescriptorsCsvFile + '.csv'

            with open(csv_path, 'r') as fin:
                dr = csv.DictReader(fin)
                for i in dr:
                    db.mid_insert(i[id_column], i[id_column])
                    logger.debug("parse_moduleinstances_file: adding moduleInstanceDescriptor {i[id_column]}")

class Workflows_parser:
    @staticmethod
    def parse_workflow_descriptors(config_root, db, logger):
        root = ET.parse(config_root/"RegionConfigFiles/WorkflowDescriptors.xml").getroot()

        for wfd in root.findall('fews:workflowDescriptor', ns):
            wf_id = wfd.attrib["id"]
            try:
                description = wfd.find('fews:description', ns).text
            except AttributeError:
                description = wf_id
            try:
                workflowFileName = wfd.find('fews:workflowFileName', ns).text
            except AttributeError:
                workflowFileName = wf_id

            # optional properties
            properties_set = {}
            for properties in wfd.findall('fews:properties', ns):
                [properties_set.update({x.attrib["key"]: x.attrib["value"]}) for x in properties if x.tag != r'{http://www.wldelft.nl/fews}description']
            for properties in wfd.findall('fews:moduleConfigProperties', ns):
                [properties_set.update({x.attrib["key"]: x.attrib["value"]}) for x in properties if x.tag != r'{http://www.wldelft.nl/fews}description']

            psid = db.insert_props_set(properties_set, logger)
            csid = db.add_call_stack(wf_id, description, workflowFileName, None, psid)
            logger.debug(f"parse_workflow_descriptors: {wf_id}; cs {csid}; psid {psid} -> {properties_set}")

    @staticmethod
    def loop_workflows(config_root, db, logger):
        # start looping through workflowfiles
        for parent in db.list_wfs():
            Workflows_parser.recurse_into_tasks(db, config_root, parent, logger)

    @staticmethod
    def recurse_into_tasks(db, config_root, parent, logger):
        (pcsid, pwfid, pwffn, ppsid) = parent
        logger.info(f"recurse_into_tasks(wf_id: {pwfid}; wffn: {pwffn})")
         # get the parent properties set
        pps = db.get_props_set(ppsid, logger)
        # load wf_file into tree
        wf_filepath = Workflows_parser.get_path_of_workflowfile(config_root, pwffn)
        # for testing
        config_file_name = wf_filepath.name
        wf_root = ET.parse(wf_filepath).getroot()

        properties_changed = False
        # read wf global properties and add/overwrite pps
        wf_ps = Workflows_parser.get_props(wf_root, pps)
        if wf_root.find('fews:properties', ns):
            properties_changed = True

        # TODO: not supported yet: <sequence>, <parallel>, <completed>
        # loop over activities: start recursion
        for activity in wf_root.findall('fews:activity', ns):
            predefinedActivity = Helpers.find_element(activity, 'fews:predefinedActivity', ns)
            new_wfid = Helpers.find_element(activity, 'fews:workflowId', ns)

            if predefinedActivity:
                logger.info(f"Skipping predefinedActivity {predefinedActivity}")
                continue
            elif new_wfid:
                # does the wf have a descriptor?
                existing_cs = db.get_call_stack_from_wfid(new_wfid, logger)
                (not_used, desc, new_wffn, new_ps) = existing_cs if existing_cs else (None, None, new_wfid, None)

                # read wf properties and add/overwrite pps
                new_ps = Workflows_parser.get_props(activity, wf_ps)
                if activity.find('fews:properties', ns):
                    properties_changed = True

                # in case of new properties: define a new properties set
                new_psid = db.insert_props_set(new_ps, logger) if properties_changed else ppsid

                new_cs = db.add_call_stack(new_wfid, desc, new_wffn, pcsid, new_psid)
                Workflows_parser.recurse_into_tasks(db, config_root, (new_cs, new_wfid, new_wffn, new_psid), logger)
            else:
                # we reached the call to the module file
                moduleInstanceId = Helpers.find_element(activity, 'fews:moduleInstanceId', ns)
                moduleConfigFileName = Helpers.find_element(activity, 'fews:moduleConfigFileName', ns)

                # read wf properties and add/overwrite pps
                new_ps = Workflows_parser.get_props(activity, wf_ps)
                if activity.find('fews:properties', ns) or moduleConfigFileName:
                    properties_changed = True

                if moduleConfigFileName:
                    new_ps.update({'MODULE_INSTANCE_ID': Helpers.solve_props(moduleInstanceId, new_ps)})
                else:
                    moduleConfigFileName = moduleInstanceId

                # in case the wf has properties: define a new properties set
                new_psid = db.insert_props_set(new_ps, logger) if properties_changed else ppsid

                # add call stack and current properties set to the database
                logger.debug ("{} called by {} with properties id {}-> {}".format(moduleConfigFileName, pwffn, new_psid, new_ps))
                db.add_modins_calls(moduleConfigFileName, pcsid, new_psid)
                new_ps = None

    @staticmethod
    def get_props(root, props):
        new_props = copy.deepcopy(props)
        try:
            [new_props.update({prop.attrib["key"]: prop.attrib["value"]}) for prop in root.find('fews:properties', ns)]
        finally:
            return new_props

    @staticmethod
    def get_path_of_workflowfile(croot, wffn):
        wf_filename = f"{wffn}.xml"
        workflow_folder = croot / "WorkflowFiles"
        for wf_filepath in workflow_folder.glob(f"**/{wf_filename}"):
            return wf_filepath

class Endpoint_parsers:
    @staticmethod
    def parse_endpoint(db, config_root, type, logger):
        for cf_filepath in config_root.glob(f"**/*.xml"):
            cf_root = ET.parse(cf_filepath).getroot()
            if cf_root.tag == r'{http://www.wldelft.nl/fews}' + type:
                logger.info(cf_filepath)
                for ix, itss in enumerate(Helpers.find_element_recursive(cf_root, 'fews:timeSeriesSet', [], ns, logger)):
                    logger.debug(f"type {type}: tss no: {ix}")
                    tss = TimeseriesSetParser.parse_tss(itss, {})
                    tss_id = db.get_tss_id(tss, logger)
                    db.add_endpoint(tss_id, type, logger)

class Modins_parser:
    @staticmethod
    def get_path_of_modinsfile(croot, mi_fn):
        mi_filename = f"{mi_fn}.xml"
        modins_folder = croot / "ModuleConfigFiles"
        for mi_filepath in modins_folder.glob(f"**/{mi_filename}"):
            return mi_filepath

    @staticmethod
    def filter_vars_from_expression(expression):
        new_words_set = set()
        [new_words_set.add(w) for w in expression.split() if not Helpers.is_float(w)]
        new_words_set = new_words_set.difference(symbols_delimiters)

        old_length = 0
        new_length = len(new_words_set)

        while new_length > old_length:
            old_words_set = set()
            old_words_set = old_words_set.union(new_words_set)
            old_length = new_length
            new_words_set = set()
            for w1 in old_words_set:
                if not Helpers.is_float(w1):
                    for d in symbols_delimiters:
                        w1 = " ".join(w1.split(d))
                    [new_words_set.add(w2) for w2 in w1.split() if not Helpers.is_float(w2)]
            new_words_set = new_words_set.difference(symbols_strings)
            new_words_set = new_words_set.difference(symbols_delimiters)
            new_length = len(new_words_set)

        return new_words_set

    @staticmethod
    def add_input(db, config_file, input, props, mic_id, ord_nr, trafo_desc, variables, ns, logger):
        if Helpers.find_tag(input, 'fews:variableId', ns):
            vid = Helpers.solve_props(Helpers.find_element(input, 'fews:variableId', ns), props)
            db.add_input(mic_id, ord_nr, trafo_desc, config_file, variables[vid], logger)
            logger.debug("input: {}".format(variables[vid]))
        else:
            tss_elem = input.find('fews:timeSeriesSet', ns)
            if tss_elem is None:
                logger.error(f"Critical error: Missing required timeSeriesSet in inputVariable for transformation {trafo_desc}")
                return
            
            tss = TimeseriesSetParser.parse_tss(tss_elem, props, mic_id)
            tss_id = db.get_tss_id(tss, logger)
            db.add_input(mic_id, ord_nr, trafo_desc, config_file, tss_id, logger)
            logger.debug("input: {}".format(tss))

    @staticmethod
    def add_output(db, config_file, output, props, mic_id, ord_nr, trafo_desc, variables, ns, logger):
        if Helpers.find_tag(output, 'fews:variableId', ns):
            vid = Helpers.solve_props(Helpers.find_element(output, 'fews:variableId', ns), props)
            db.add_output(mic_id, ord_nr, trafo_desc, config_file, variables[vid], logger)
            logger.debug("output: {}".format(variables[vid]))
        else:
            tss_elem = output.find('fews:timeSeriesSet', ns)
            if tss_elem is None:
                logger.error(f"Critical error: Missing required timeSeriesSet in outputVariable for transformation {trafo_desc}")
                return
            
            tss = TimeseriesSetParser.parse_tss(tss_elem, props, mic_id)
            tss_id = db.get_tss_id(tss, logger)
            db.add_output(mic_id, ord_nr, trafo_desc, config_file, tss_id, logger)
            logger.debug("output: {}".format(tss))

    @staticmethod
    def parse_modins(db, config_root, logger):
        n_modins_calls = db.get_n_modins_calls()
        logger.info(f"Looping over {n_modins_calls}")
        i_call_stacks = 1
        for mic_id, modins_fn, cs_id, ps_id in db.list_modins():
            # get properties set for this modins
            props = db.get_props_set(ps_id, logger)

            logger.info(f"{i_call_stacks}/{n_modins_calls}: {modins_fn}; props -> {props}")
            i_call_stacks = i_call_stacks + 1

            mi_file_path = Modins_parser.get_path_of_modinsfile(config_root, modins_fn)
            config_file = (mi_file_path.as_posix()).replace(config_root.as_posix(), "")
            mi_root = ET.parse(mi_file_path).getroot()

            if mi_root.tag == r'{http://www.wldelft.nl/fews}transformationModule':
                # collect variables
                variables = {}
                for var in mi_root.findall('fews:variable', ns):
                    var_id = Helpers.solve_props(var.find('fews:variableId', ns).text, props)
                    tss = TimeseriesSetParser.parse_tss(var.find('fews:timeSeriesSet', ns), props, mic_id)
                    tss_id = db.get_tss_id(tss, logger)
                    variables[var_id] = tss_id
                    logger.debug(f"{var_id}: {tss}")
                # loop transformations
                ord_nr = 0
                for trafo in mi_root.findall('fews:transformation', ns):
                    trafo_desc = Helpers.solve_props(trafo.attrib['id'], props)
                    ord_nr = ord_nr + 1
                    # collect local input variables
                    local_vars = {}
                    for element in ['fews:inputVariableDefinition', 'fews:limitVariable', \
                                    'fews:nonEquidistantInputVariable', 'fews:equidistantInputVariable' \
                                    'fews:timeReferenceInputVariable', 'fews:inputVariable']:
                        for input in Helpers.find_element_recursive(trafo, element, [], ns, logger):
                            vid = Helpers.solve_props(Helpers.find_element(input, 'fews:variableId', ns), props)

                            template_vid = Helpers.solve_props(Helpers.find_element(input, 'fews:templateVariableId', ns), props)
                            # TODO: we will need the locid when we will be solving the locationsets
                            # locid = Helpers.solve_props(Helpers.find_element(input, 'fews:locationId', ns), props)
                            if template_vid:
                                logger.debug(f"Template variable {template_vid} found in {element} for transformation {trafo_desc}")
                                tss_id = variables[template_vid]
                                local_vars[vid] = tss_id
                                tss = db.get_tss(tss_id, logger) # only to log it
                                # TODO: do something with the locid
                            else:
                                if vid not in variables:
                                    tss_elem = input.find('fews:timeSeriesSet', ns)
                                    if tss_elem is None:
                                        logger.error(f"Critical error: Missing required timeSeriesSet in {element} for transformation {trafo_desc}")
                                        continue
                                    tss = TimeseriesSetParser.parse_tss(tss_elem, props, mic_id)
                                    tss_id = db.get_tss_id(tss, logger)
                                    local_vars[vid] = tss_id
                                else:
                                    tss_id = variables[vid]
                                    tss = db.get_tss(tss_id, logger) # only to log it

                            # here we assume that in case a variable is defined in a trafo, it will also be used
                            db.add_input(mic_id, ord_nr, trafo_desc, config_file, tss_id, logger)
                            logger.debug("input: {}".format(tss))

                    # collect outputs
                    for output in Helpers.find_element_recursive(trafo, 'fews:outputVariable', [], ns, logger):
                        Modins_parser.add_output(db, config_file, output, props, mic_id, ord_nr, trafo_desc, variables | local_vars, ns, logger)

                    # for <user><simple> find coefficients and local variables
                    # user simple coefficients
                    coefficients = set()
                    for coefficient in Helpers.find_element_recursive(trafo, 'fews:coefficient', [], ns, logger):
                        coefficients.add(coefficient.attrib['id'])
                        logger.debug("coefficient: {}".format(coefficient.attrib['id']))
                    # add coefficients from coefficientset files
                    cs = ""
                    for coefficientSet in Helpers.find_element_recursive(trafo, 'fews:coefficientSetId', [], ns, logger):
                        cs = coefficientSet.text
                    cs_fn = ""
                    for coefficientSetFile in Helpers.find_element_recursive(trafo, 'fews:coefficientSetFile', [], ns, logger):
                        cs_fn = coefficientSetFile.text
                    if cs and cs_fn:
                        cs_id = "{}_{}".format(cs_fn, cs)
                        coefficients = coefficients.union(coefficientSets[cs_id])

                    # user simple
                    for input in Helpers.find_element_recursive(trafo, 'fews:expression', [], ns, logger):
                        # solve references tss in expression, vars and trafo_vars, but skip coefficients
                        words = Modins_parser.filter_vars_from_expression(Helpers.solve_props(input.text, props))
                        words = words.difference(coefficients)      # ignore coefficients
                        words = words.difference(local_vars)        # ignore local variables: these have already been added
                        logger.debug(words)
                        # the remaining words should be variables at module level
                        for w in words:
                            if w in variables:
                                db.add_input(mic_id, ord_nr, trafo_desc, config_file, variables[w], logger)
                            else:
                                logger.warning(f"Variable '{w}' not found in variables dictionary for transformation '{trafo_desc}'")

                    # structure functions
                    for input in Helpers.find_element_recursive(trafo, 'fews:structure', [], ns, logger):
                        for element in ['fews:limitVariable', 'fews:status', 'fews:speed', 'fews:head', 'fews:headlevel', 'fews:taillevel', 'fews:height']:
                            for sub_elem in Helpers.find_element_recursive(input, element, [], ns, logger):
                                Modins_parser.add_input(db, config_file, sub_elem, props, mic_id, ord_nr, trafo_desc, variables, ns, logger)

                        for sub_elem in Helpers.find_element_recursive(input, 'fews:discharge', [], ns, logger):
                            Modins_parser.add_output(db, config_file, sub_elem, props, mic_id, ord_nr, trafo_desc, variables, ns, logger)


            # GENERAL ADAPTER
            elif mi_root.tag == r'{http://www.wldelft.nl/fews}generalAdapterRun':
                inputs = ['fews:exportTimeSeriesActivity', 'fews:exportNetcdfActivity', 'fews:exportCustomFormatTimeSeriesActivity']
                outputs = ['fews:importTimeSeriesActivity', 'fews:importNetcdfActivity', 'fews:importCustomFormatTimeSeriesActivity']
                logger.debug("generalAdapterRun")
                ord_nr = 0
                for ac in mi_root.findall('fews:activities', ns):
                    for exac in ac.findall('fews:exportActivities', ns):
                        for tsea in Helpers.find_element_recursive(exac, inputs, [], ns, logger):
                            for tsss in Helpers.find_element_recursive(tsea, 'fews:timeSeriesSets', [], ns, logger):
                                for itss in tsss.findall('fews:timeSeriesSet', ns):
                                    tss = TimeseriesSetParser.parse_tss(itss, props, mic_id)
                                    tss_id = db.get_tss_id(tss, logger)
                                    ord_nr = ord_nr + 1
                                    db.add_input(mic_id, ord_nr, modins_fn, config_file, tss_id, logger)

                    for imac in ac.findall('fews:importActivities', ns):
                        for tsia in Helpers.find_element_recursive(imac, outputs, [], ns, logger):
                            for tsss in Helpers.find_element_recursive(tsia, 'fews:timeSeriesSets', [], ns, logger):
                                for itss in tsss.findall('fews:timeSeriesSet', ns):
                                    tss = TimeseriesSetParser.parse_tss(itss, props, mic_id)
                                    tss_id = db.get_tss_id(tss, logger)
                                    ord_nr = ord_nr + 1
                                    db.add_output(mic_id, ord_nr, modins_fn, config_file, tss_id, logger)
            # imports                
            elif mi_root.tag == r'{http://www.wldelft.nl/fews}timeSeriesImportRun':
                logger.debug(mi_root.tag)
                ord_nr = 0
                for tsss in Helpers.find_element_recursive(mi_root, 'fews:timeSeriesSet', [], ns, logger):
                    tss = TimeseriesSetParser.parse_tss(tsss, props, mic_id)
                    tss_id = db.get_tss_id(tss, logger)
                    ord_nr = ord_nr + 1
                    db.add_output(mic_id, ord_nr, modins_fn, config_file, tss_id, logger)
                    db.add_endpoint(tss_id, modins_fn, logger)
            # exports and reports
            elif mi_root.tag in {r'{http://www.wldelft.nl/fews}timeSeriesExportRun', r'{http://www.wldelft.nl/fews}reports', r'{http://www.wldelft.nl/fews}exportArchiveModule'}:
                logger.debug(mi_root.tag)
                ord_nr = 0
                for tsss in Helpers.find_element_recursive(mi_root, 'fews:timeSeriesSet', [], ns, logger):
                    tss = TimeseriesSetParser.parse_tss(tsss, props, mic_id)
                    tss_id = db.get_tss_id(tss, logger)
                    ord_nr = ord_nr + 1
                    db.add_input(mic_id, ord_nr, modins_fn, config_file, tss_id, logger)
                    db.add_endpoint(tss_id, modins_fn, logger)
            elif mi_root.tag in ignored_modules:
                continue
            else:
                logger.warn("Unrecognized module named: {}; with type: {}".format(modins_fn, mi_root.tag))

class CoefficientSet_parser:
    @staticmethod
    def parse(config_root, logger):
        for cf_filepath in (config_root).glob(f"**/*.xml"):
            cf_root = ET.parse(cf_filepath).getroot()
            if cf_root.tag == r'{http://www.wldelft.nl/fews}' + 'transformationCoefficientSets':
                logger.debug(cf_filepath)
                for ics in Helpers.find_element_recursive(cf_root, 'fews:coefficientSet', [], ns, logger):
                    cs_id = "{}_{}".format(cf_filepath.stem, ics.attrib['id'])
                    coefficients = set()
                    [coefficients.add(ic.attrib['id']) for ic in Helpers.find_element_recursive(ics, 'fews:coefficient', [], ns, logger)]
                    coefficientSets[cs_id] = coefficients