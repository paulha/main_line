import logging
from utility_funcs.search import get_server_info
from jama_client import JamaClient


class Jama:

    def __init__(self, server_alias, config_path, log=logging.getLogger("root"), threads=32):
        self.server_alias = server_alias
        self.log = log
        self.jama_config = None
        self.projects = None
        self.item_types = None
        self.platforms = None
        self.tree = None
        self.id = None      # ID of tree root

        # -- Get JAMA login configuration and authentication info
        try:
            self.jama_config = get_server_info(server_alias, config_path)  # possible FileNotFoundError
        except FileNotFoundError as f:
            self.log.fatal("Can't open JAMA authentication configuration file: %s" % f)
            raise FileNotFoundError("Can't find JAMA configuration file", config_path)

        self.log.info("Using JAMA server %s, '%s'", server_alias, self.jama_config['host'])
        self.jama_client = JamaClient(self.jama_config, threads=threads)

    def get_projects(self):
        # -- Used to get project ID from project name
        if self.projects is None:
            self.projects = {p['fields']['projectKey']: p for p in self.jama_client.get_all('projects') if
                             'projectKey' in p['fields']}
        return self.projects

    def get_platforms(self, project: object) -> object:
        if self.platforms is None:
            self.platforms = {node['fields']['name']: node
                              for node in self.jama_client.get_all('items/?project={}&rootOnly=true'
                                                                   .format(project['id']))}
        return self.platforms

    def get_tree(self, entry, use_multithreading=True):
        item_id = entry if isinstance(entry, int) else entry['id']
        if self.tree is None or self.id != item_id:
            self.id = item_id
            self.tree = self.jama_client.get_descendants(self.id, use_multithreading)
        return self.tree

    def get_item_type_entry(self, name=None, id=None, item=None):
        result = None
        if name is not None and isinstance(name, str):
            result = self.jama_client.get_itemtype_by_name(name)
        elif id is not None and isinstance(name, int):
            result = self.jama_client.get_itemtype_by_id(item['id'])
        elif item is not None and isinstance(name, object):
            # -- Depending on what the object is, way to get type might change...
            result = self.jama_client.get_itemtype_by_id(item['itemType'])
        else:
            raise TypeError("Invalid argument")
        return result

    def get_fieldtype_by_name(self, itemtype, name):
        item = self.get_itemtype_by_name(itemtype)
        fieldtype = item['fields']
        for field in fieldtype:
            if field['label'] == name:
                return field

    def get_real_field_name(self, jama_item, name_to_look_up):
        return self.jama_client.get_real_field_name(jama_item, name_to_look_up)

    def get_real_field_value(self, jama_item, name_to_look_up):
        return self.jama_client.get_real_field_value(jama_item, name_to_look_up)

    def get_itemtype_by_name(self, name):
        return self.jama_client.get_itemtype_by_name(name)

    def get_itemtype_by_id(self, id):
        return self.jama_client.get_itemtype_by_id(id)

    def get_picklist_options(self, id):
        return self.jama_client.get_picklist_options(id)
