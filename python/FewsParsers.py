import xml.etree.ElementTree as ET
from Helpers import Helpers
import copy


ns = {'fews': 'http://www.wldelft.nl/fews'}
# user simple symbols
# N.B. some of these html symbols are interpreted by python: therefore &gt; and >
symbols_delimiters = ['+','-','/','*','^','&gt;','>','&lt;','<','&gt;=','&lt;=','=','!','(',')','||',',']
symbols_strings = ['isMissing','if','or','and','sin','cos','tan','asin','acos','atan','sinh','cosh', \
                   'tanh','asinh','acosh','atanh','log','ln','exp','sqrt','abs','pow','max','min', 'pi', '']
ignored_modules = { r'{http://www.wldelft.nl/fews}reportExport', \
                    r'{http://www.wldelft.nl/fews}secondaryValidation', \
                    r'{http://www.wldelft.nl/fews}importAmalgamate',  \
                    r'{http://www.wldelft.nl/fews}configUpdateModule', \
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
            tsid_map[timestep['id']] = timestepstring

    @staticmethod
    def parse_tss(root_tss, props):
        moduleInstanceId = Helpers.solve_props(root_tss.find('fews:moduleInstanceId', ns).text, props)
        valueType = Helpers.solve_props(root_tss.find('fews:valueType', ns).text, props)
        parameterId = Helpers.solve_props(root_tss.find('fews:parameterId', ns).text, props)
        timeSeriesType = Helpers.solve_props(root_tss.find('fews:timeSeriesType', ns).text, props)

        # multiple qualifiers are possible
        q_list = []
        qualifiers = ""
        [q_list.append(Helpers.solve_props(q.text, props)) for q in root_tss.findall('fews:qualifierId', ns)]
        for q in sorted(q_list):
            if len(qualifiers) > 0:
                qualifiers = qualifiers + '/' + q
            else:
                qualifiers = q

        timestep = {'id': "", 'multiplier': "", 'unit': "", 'timeZone': ""}
        [timestep.update({key: Helpers.solve_props(value, props)}) for key, value in root_tss.find('fews:timeStep', ns).items()]
        if timestep.get('id'):
            timestepstring = tsid_map[timestep['id']]
        else:
            timestepstring = "{}{}{}".format(timestep['multiplier'], timestep['unit'], timestep['timeZone'])

        return (moduleInstanceId, valueType, parameterId, qualifiers, timeSeriesType, timestepstring)

class Workflows_parser:
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

    @staticmethod
    def recurse_into_tasks(db, config_root, wf_id, cps, ccs, logger):
        logger.info("recurse_into_tasks(wf_id -> {})".format(ccs))
        # load wf_file into tree
        wffn = db.get_workflow_filename(wf_id, logger)
        wf_filepath = Workflows_parser.get_path_of_workflowfile(config_root, wffn)
        wf_root = ET.parse(wf_filepath).getroot()

        # read wff global properties and add/overwrite cps
        cps = Workflows_parser.get_props(wf_root, cps)

        # loop over activities: start recursion
        for activity in wf_root.findall('fews:activity', ns):
            predefinedActivity = Helpers.find_element(activity, 'fews:predefinedActivity', ns)
            workflowId = Helpers.find_element(activity, 'fews:workflowId', ns)

            if predefinedActivity:
                logger.info(f"Skipping predefinedActivity {predefinedActivity}")
                continue
            elif workflowId:
                new_ccs = copy.deepcopy(ccs)
                new_ccs.append(workflowId)
                new_cps = Workflows_parser.get_props(activity, cps)
                Workflows_parser.recurse_into_tasks(db, config_root, workflowId, new_cps, new_ccs, logger)
                del(new_ccs)
            else:
                # we reached the call to the module file
                new_cps = Workflows_parser.get_props(activity, cps)
                moduleInstanceId = Helpers.find_element(activity, 'fews:moduleInstanceId', ns)
                moduleConfigFileName = Helpers.find_element(activity, 'fews:moduleConfigFileName', ns)
                if not moduleConfigFileName:
                    moduleConfigFileName = moduleInstanceId
                # add call stack and current properties set to the database
                logger.debug ("{} called by {} with properties {}".format(moduleConfigFileName, ccs, new_cps))
                db.add_call_stack_and_props(moduleConfigFileName, ccs, new_cps, logger)

        #logger.debug("leaving recursion")

    @staticmethod
    def parse_workflows(config_root, db, logger):
        root = ET.parse(config_root/"RegionConfigFiles/WorkflowDescriptors.xml").getroot()

        for wfd in root.findall('fews:workflowDescriptor', ns):
            wf_id = wfd.attrib["id"]
            description = wfd.find('fews:description', ns).text
            try:
                workflowFileName = wfd.find('fews:workflowFileName', ns).text
            except AttributeError:
                workflowFileName = wf_id

            # optional properties
            current_properties_set = {}
            for properties in wfd.findall('fews:properties', ns):
                [current_properties_set.update({x.attrib["key"]: x.attrib["value"]}) for x in properties if x.tag != r'{http://www.wldelft.nl/fews}description']
            for properties in wfd.findall('fews:moduleConfigProperties', ns):
                [current_properties_set.update({x.attrib["key"]: x.attrib["value"]}) for x in properties if x.tag != r'{http://www.wldelft.nl/fews}description']
 
            # properties set can be empty
            if len(current_properties_set) > 0:
                cps_id = db.insert_props_set(current_properties_set, logger)
            else:
                cps_id = None

            db.wfs_insert(wf_id, description, workflowFileName, cps_id)

    @staticmethod
    def loop_workflows(config_root, db, logger):
        # start looping through workflowfiles
        ncount = 0
        for row in db.list_wfs():
            ncount = ncount + 1
            wf_id = row[0]
            props_set_id = row[2]
            # create dictionary of current properties set (cps) from wfd_props
            if props_set_id:
                cps = db.get_props_set(props_set_id, logger)
            else:
                cps = {}
            # create array with the current call stack (ccs) from wfs
            ccs = [wf_id]

            Workflows_parser.recurse_into_tasks(db, config_root, wf_id, cps, ccs, logger)
            # TODO: not supported yet: <sequence>, <parallel>, <completed>
            logger.debug(f"{ncount} workflows analyzed")

class Endpoint_parsers:
    @staticmethod
    def parse_endpoint(db, config_root, type, logger):
        for cf_filepath in config_root.glob(f"**/*.xml"):
            cf_root = ET.parse(cf_filepath).getroot()
            if cf_root.tag == r'{http://www.wldelft.nl/fews}' + type:
                logger.info(cf_filepath)
                for itss in Helpers.find_element_recursive(cf_root, 'fews:timeSeriesSet', [], ns, logger):
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
    def parse_modins(db, config_root, logger):
        n_modins_calls = db.get_n_modins_calls()
        logger.info(f"Looping over {n_modins_calls}")
        i_call_stacks = 1
        for mic_id, modins_fn, cs_id, ps_id in db.list_modins():
            logger.info(f"{i_call_stacks}/{n_modins_calls}: {modins_fn}")
            i_call_stacks = i_call_stacks + 1

            # get properties set for this modins
            props = db.get_props_set(ps_id, logger)

            mi_file_path = Modins_parser.get_path_of_modinsfile(config_root, modins_fn)
            mi_root = ET.parse(mi_file_path)

            if mi_root.tag == r'{http://www.wldelft.nl/fews}transformationModule':
                # collect variables
                variables = {}
                for var in mi_root.findall('fews:variable', ns):
                    var_id = Helpers.solve_props(var.find('fews:variableId', ns).text, props)
                    tss = TimeseriesSetParser.parse_tss(var.find('fews:timeSeriesSet', ns), props)
                    tss_id = db.get_tss_id(tss, logger)
                    variables[var_id] = tss_id
                    logger.debug(f"{var_id}: {tss}")
                # loop transformations
                ord_nr = 0
                for trafo in mi_root.findall('fews:transformation', ns):
                    trafo_desc = Helpers.solve_props(trafo.attrib['id'], props)
                    ord_nr = ord_nr + 1
                    # collect inputs
                    for input in Helpers.find_element_recursive(trafo, 'fews:inputVariable', [], ns, logger):
                        if Helpers.find_tag(input, 'fews:variableId', ns):
                            vid = Helpers.solve_props(Helpers.find_element(input, 'fews:variableId', ns), props)
                            db.add_input(mic_id, ord_nr, trafo_desc, variables[vid], logger)
                            logger.debug("input: {}".format(variables[vid]))
                        else:
                            tss = TimeseriesSetParser.parse_tss(input.find('fews:timeSeriesSet', ns), props)
                            tss_id = db.get_tss_id(tss, logger)
                            db.add_input(mic_id, ord_nr, trafo_desc, tss_id, logger)
                            logger.debug("input: {}".format(tss))

                    # collect outputs
                    for output in Helpers.find_element_recursive(trafo, 'fews:outputVariable', [], ns, logger):
                        if Helpers.find_tag(output, 'fews:variableId', ns):
                            vid = Helpers.solve_props(Helpers.find_element(output, 'fews:variableId', ns), props)
                            db.add_output(mic_id, ord_nr, trafo_desc, variables[vid], logger)
                            logger.debug("output: {}".format(variables[vid]))
                        else:
                            tss = TimeseriesSetParser.parse_tss(output.find('fews:timeSeriesSet', ns), props)
                            tss_id = db.get_tss_id(tss, logger)
                            db.add_output(mic_id, ord_nr, trafo_desc, tss_id, logger)
                            logger.debug("output: {}".format(tss))

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

                    # user simple local variables
                    local_vars = set()
                    for input in Helpers.find_element_recursive(trafo, 'fews:inputVariableDefinition', [], ns, logger):
                        vid = Helpers.solve_props(Helpers.find_element(input, 'fews:variableId', ns), props)
                        tss = TimeseriesSetParser.parse_tss(input.find('fews:timeSeriesSet', ns), props)
                        tss_id = db.get_tss_id(tss, logger)
                        local_vars.add(vid)
                        # here we assume that in case a variable is defined in a trafo, it will also be used
                        db.add_input(mic_id, ord_nr, trafo_desc, tss_id, logger)
                        logger.debug("input: {}".format(tss))

                    # user simple
                    for input in Helpers.find_element_recursive(trafo, 'fews:expression', [], ns, logger):
                        # solve references tss in expression, vars and trafo_vars, but skip coefficients
                        words = Modins_parser.filter_vars_from_expression(input.text)
                        words = words.difference(coefficients)      # ignore coefficients
                        words = words.difference(local_vars)        # ignore local variables: these have already been added
                        logger.debug(words)
                        # the remaining words should be variables at module level
                        [db.add_input(mic_id, ord_nr, trafo_desc, variables[w], logger) for w in words]

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
                                    tss = TimeseriesSetParser.parse_tss(itss, props)
                                    tss_id = db.get_tss_id(tss, logger)
                                    ord_nr = ord_nr + 1
                                    db.add_input(mic_id, ord_nr, modins_fn, tss_id, logger)

                    for imac in ac.findall('fews:importActivities', ns):
                        for tsia in Helpers.find_element_recursive(imac, outputs, [], ns, logger):
                            for tsss in Helpers.find_element_recursive(tsia, 'fews:timeSeriesSets', [], ns, logger):
                                for itss in tsss.findall('fews:timeSeriesSet', ns):
                                    tss = TimeseriesSetParser.parse_tss(itss, props)
                                    tss_id = db.get_tss_id(tss, logger)
                                    ord_nr = ord_nr + 1
                                    db.add_output(mic_id, ord_nr, modins_fn, tss_id, logger)
            # imports                
            elif mi_root.tag == r'{http://www.wldelft.nl/fews}timeSeriesImportRun':
                logger.debug(mi_root.tag)
                ord_nr = 0
                for tsss in Helpers.find_element_recursive(mi_root, 'fews:timeSeriesSet', [], ns, logger):
                    tss = TimeseriesSetParser.parse_tss(itss, props)
                    tss_id = db.get_tss_id(tss, logger)
                    ord_nr = ord_nr + 1
                    db.add_output(mic_id, ord_nr, modins_fn, tss_id, logger)
                    db.add_endpoint(tss_id, modins_fn, logger)
            # exports and reports
            elif mi_root.tag in {r'{http://www.wldelft.nl/fews}timeSeriesExportRun', r'{http://www.wldelft.nl/fews}reports'}:
                logger.debug(mi_root.tag)
                ord_nr = 0
                for tsss in Helpers.find_element_recursive(mi_root, 'fews:timeSeriesSet', [], ns, logger):
                    tss = TimeseriesSetParser.parse_tss(itss, props)
                    tss_id = db.get_tss_id(tss, logger)
                    ord_nr = ord_nr + 1
                    db.add_input(mic_id, ord_nr, modins_fn, tss_id, logger)
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
