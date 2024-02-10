class Helpers:
    @staticmethod
    def is_float(float_str: str) -> bool:
        try:
            f = float(float_str)
            return True
        except ValueError:
            return False

    @staticmethod
    def find_element(root, search_string, ns):
        try:
            return root.find(search_string, ns).text
        except:
            return ""

    @staticmethod
    def find_tag(root, search_string, ns):
        try:
            return root.find(search_string, ns).tag
        except:
            return ""

    @staticmethod
    def solve_props(text, props):
        for key, value in props.items():
            search = f"${key}$"
            text = text.replace(search, value)
        return text

    @staticmethod
    def find_element_recursive(root, strings, inputs, ns, logger):
        logger.debug("root.tag: {}".format(root.tag))
        # search for string at this level
        if isinstance(strings, list):
            search_strings = strings
        else:
            search_strings = [strings]

        level_count = 0
        for search_string in search_strings:
            for inp in root.findall(search_string, ns):
                logger.debug(f"{search_string} found")
                level_count = level_count + 1
                inputs.append(inp)
        # when found at this level return them
        if level_count > 0:
            return inputs
        else:
            # if not found: search deeper
            for child in root:
                inputs = Helpers.find_element_recursive(child, search_string, inputs, ns, logger)
            return inputs

