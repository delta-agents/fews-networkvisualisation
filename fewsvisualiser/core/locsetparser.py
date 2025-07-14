import xml.etree.ElementTree as ET


ns = {'fews': 'http://www.wldelft.nl/fews'}

class Locset_parser:

    @staticmethod
    def parse_attributes(ls, db, locset_id, source, logger):
        for attr in ls.findall('fews:attribute', ns):
            attribute = {'id': "", 'name': "", 'locset_id': "", 'source': "", 'field': ""}  # Initialize with default values
            [attribute.update({key: value}) for key, value in attr.attrib.items()]
            if not attribute['name']:
                attribute['name'] = attribute['id']
            attribute['locset_id'] = locset_id
            attribute['source'] = source

            # 'fews:description', 
            for attr_tag in ['fews:boolean', 'fews:dateTime', 'fews:number', 'fews:text']:
                try:
                    field = attr.find(attr_tag, ns)
                    if field is not None and field.text:
                        attribute['field'] = field.text.strip("%")
                        db.insert_attribute(attribute, logger)
                        break
                except AttributeError:
                    pass





    @staticmethod
    def parse_locationsets(config_root, db, logger):
        locset_path = config_root / "RegionConfigFiles" / "LocationSets.xml"
        logger.debug(f"Parsing {locset_path}")
        lsid_root = ET.parse(locset_path).getroot()
        for ls in lsid_root.findall('fews:locationSet', ns):
            locset = {'id': "", 'name': "", 'source': ""}
            [locset.update({key: value}) for key, value in ls.attrib.items()]
            if not locset['name']:
                locset['name'] = locset['id']

            # find source file if it exists
            for filetag in ['fews:csvFile', 'fews:esriShapeFile']:
                try:
                    for source_root in ls.findall(filetag, ns):
                        for file in source_root.findall('fews:file', ns):
                            if file.text:
                                file = file.text.strip()
                                # add .csv or .dbf extension if not present
                                if not file.endswith(('.csv', '.dbf')):
                                    file += '.csv' if filetag == 'fews:csvFile' else '.dbf'
                                locset['source'] = file
                                break
                except AttributeError:
                    pass

            # find database table if it exists
            if ls.find('fews:table', ns) is not None:
                for tab_element in ls.findall('fews:table', ns):
                    locset['source'] = tab_element.find('fews:name', ns).text.strip()

            print(f"LocationSet: {locset}")
            db.insert_locset(locset, logger)

            # find parent locationset if it exists
            for parent in ls.findall('fews:locationSetId', ns):
                parent_id = parent.text.strip()
                db.insert_locset_relation(locset['id'], parent_id, logger)
           
            # parse attributes
            Locset_parser.parse_attributes(ls, db, locset['id'], locset['source'], logger)

        

