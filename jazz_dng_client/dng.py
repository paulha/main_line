
# from .artifacts import Folder, RequirementRequest, RequirementCollection
# -- Support
import sys
from os.path import pathsep, dirname, realpath

from lxml import etree
import pandas as pd
import requests
from urllib.parse import urlencode
import urllib3
import utility_funcs.logger_yaml as log

from utility_funcs.search import get_server_info
import re

urllib3.disable_warnings()

# -- Set up logger...
LOG_CONFIG_FILE = 'logging.yaml'+pathsep+dirname(realpath(sys.argv[0]))+'/logging.yaml'
log.setup_logging("logging.yaml", override={'handlers': {'info_file_handler': {'filename': 'access_dng.log'}}})
log.logger.setLevel(log.logging.getLevelName("INFO"))
log.logger.disabled = False

JAZZ_CONFIG_PATH = f"{dirname(realpath(sys.argv[0]))}/config.yaml{pathsep}~/.jazz/config.yaml"

XML_LOG_FILE = "Dialog"


class Jazz:
    @classmethod
    def xpath_namespace(cls):
        return {
            "acc": "http://open-services.net/ns/core/acc#",
            "acp": "http://jazz.net/ns/acp#",
            "calm": "http://jazz.net/xmlns/prod/jazz/calm/1.0/",
            "dc": "http://purl.org/dc/elements/1.1/",
            "dcterms": "http://purl.org/dc/terms/",
            "nav": "http://jazz.net/ns/rm/navigation#",
            "oslc": "http://open-services.net/ns/core#",
            "oslc_config": "http://open-services.net/ns/config#",
            "oslc_rm": "http://open-services.net/ns/rm#",
            "process": "http://jazz.net/ns/process#",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "rm": "http://www.ibm.com/xmlns/rdm/rdf/",
            "rm_jazz": "http://jazz.net/ns/rm#",
        }

    def get_xpath_string(self):
        return ", ".join([f"{name}=<{uri}>" for name, uri in Jazz.xpath_namespace().items()])

    def resolve_name(self, name: str):
        ns_name = name.split(":")
        if self.namespace is not None and ns_name[0] in self.namespace:
            ns_name[0] = self.namespace[ns_name[0]]
        elif ns_name[0] in self.xpath_namespace():
            ns_name[0] = self.xpath_namespace()[ns_name[0]]
        else:
            raise IndexError(f"Undefined namespace: {name}")

        return f"{{{ns_name[0]}}}{ns_name[1]}"

    def __init__(self, server_alias=None, config_path=None, namespace=None, op_name=XML_LOG_FILE, log=log, use_cache=True):
        self.xml_cache = {}
        self.use_cache = use_cache
        self.root_folder = None
        self.jazz_session = requests.Session()
        self.logger = log.logger
        self.namespace = namespace
        self.op_name = op_name
        self.reset_list = []
        self.jazz_config = None
        self._root_services = None
        self._root_services_catalogs = None
        self._service_provider = None
        self._service_provider_root = None
        self._creation_factory = None
        self._query_base = None
        self._requirement_factory = {}
        self._shapes_nodes_root = {}

        self.logger.debug("Start initialization")

        login_response = self.login(server_alias, config_path)

        root_services_catalogs = self.get_root_services_catalogs()
        self.logger.debug("Initialization completed")

    def _get_text(x):
        return x[0].text if len(x) > 0 else ""

    def _get_first(x):
        return x[0] if len(x) > 0 else None

    def get_xml(self, url, op_name=None, mode="a", check=None):
        # -- Get the XML tree into the cache
        if url not in self.xml_cache or not self.use_cache:
            op_name = self.op_name if op_name is None else op_name

            self.logger.debug(f"get_xml('{url}', {op_name})")
            response = self.jazz_session.get(url,
                                             headers={'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml'},
                                             stream=True, verify=False)
            if response.status_code >= 400 and response.status_code <= 499:
                # Error 4XX:
                logger = self.logger.error
            elif response.status_code >= 300 and response.status_code <= 399:
                # Warning 3XX:
                logger = self.logger.warning
            else:
                # Everything else...
                logger = self.logger.debug

            self.logger.debug(f"{op_name if op_name is not None else '-->'} response: {response.status_code}")
            self.logger.debug(f"{op_name if op_name is not None else '-->'} cookies: {response.cookies}")
            self.logger.debug(f"{op_name if op_name is not None else '-->'} headers: {response.headers}")
            self.logger.debug(f"{url}\n{response.text}\n====")

            if op_name is not None:
                if op_name not in self.reset_list:
                    local_mode = "w"    # FIXME: Has to be "w" but want binary...
                    self.reset_list.append(op_name)
                else:
                    local_mode = mode
                with open(op_name + '.xml', local_mode) as f:
                    f.write(f"<!-- {op_name} request:  GET {url} -->\n")
                    f.write(f"<!-- {op_name} response: {response.status_code} -->\n")
                    f.write(f"<!-- {op_name} cookies:  {response.cookies} -->\n")
                    f.write(f"<!-- {op_name} headers:  {response.headers} -->\n")
                    f.write(response.text+"\n")

            if check is not None:
                check(response)

            response.raw.decode_content = True
            root = etree.fromstring(response.text)
            # -- Set local namespace mapping from the source document
            self.namespace = root.nsmap
            # -- Preserve ETag header
            if 'ETag' in response.headers:
                root.attrib['ETag'] = response.headers['ETag']

            if self.use_cache:
                self.xml_cache[url] = root

        # -- Return the value that's in the cache.
        return self.xml_cache[url] if self.use_cache else root

    def post_xml(self, url, data=None, json=None, if_match: str=None, op_name=None, mode="a", check=None):
        op_name = self.op_name if op_name is None else op_name

        self.logger.debug(f"post_xml('{url}', {op_name})")
        headers = {'OSLC-Core-Version': '2.0',
                   'Accept': 'application/rdf+xml',
                   "Content-Type": "application/rdf+xml"}
        # -- add the If-Match ETag value as needed...
        if if_match is not None:
            headers['If-Match'] = if_match

        if self.use_cache and url in self.xml_cache:
            del self.xml_cache[url]     # remove from cache to force update

        response = self.jazz_session.post(url, data=data, json=json, headers=headers, stream=True, verify=False)

        if response.status_code >= 400 and response.status_code <= 499:
            # Error 4XX:
            logger = self.logger.error
        elif response.status_code >= 300 and response.status_code <= 399:
            # Warning 3XX:
            logger = self.logger.warning
        else:
            # Everything else...
            logger = self.logger.debug

        self.logger.debug(f"{op_name if op_name is not None else '-->'} response: {response.status_code}")
        self.logger.debug(f"{op_name if op_name is not None else '-->'} cookies: {response.cookies}")
        self.logger.debug(f"{op_name if op_name is not None else '-->'} headers: {response.headers}")
        self.logger.debug(f"{url}\n{response.text}\n====")

        if op_name is not None:
            if op_name not in self.reset_list:
                local_mode = "wb"
                self.reset_list.append(op_name)
            else:
                local_mode = mode
            with open(op_name + '.xml', local_mode) as f:
                f.write(f"<!-- {op_name if op_name is not None else '-->'} request:  POST {url} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} response: {response.status_code} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} cookies:  {response.cookies} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} headers:  {response.headers} -->\n")
                if data is not None or json is not None:
                    f.write(f"<!--\n")
                    f.write(f"{data if data is not None else json}\n")
                    f.write(f"-->\n")
                f.write(response.text+"\n")

        if check is not None:
            check(response)

        response.raw.decode_content = True
        root = None
        try:
            root = etree.fromstring(response.text)
            # -- Set local namespace mapping from the source document
            self.namespace = root.nsmap
            # -- Preserve ETag header
            if 'ETag' in response.headers:
                root.attrib['ETag'] = response.headers['ETag']
        except Exception as e:
            # Didn't get back any valid XML...
            pass

        return root

    def put_xml(self, url, data=None, if_match: str=None, op_name=None, mode="a", check=None):
        op_name = self.op_name if op_name is None else op_name

        self.logger.debug(f"put_xml('{url}', {op_name})")
        headers = {'OSLC-Core-Version': '2.0',
                   'Accept': 'application/rdf+xml',
                   "Content-Type": "application/rdf+xml"}
        # -- add the If-Match ETag value as needed...
        if if_match is not None:
            headers['If-Match'] = if_match

        if self.use_cache and url in self.xml_cache:
            del self.xml_cache[url]  # remove from cache to force update

        response = self.jazz_session.put(url, data=data, headers=headers, stream=True, verify=False)

        if response.status_code >= 400 and response.status_code <= 499:
            # Error 4XX:
            logger = self.logger.error
        elif response.status_code >= 300 and response.status_code <= 399:
            # Warning 3XX:
            logger = self.logger.warning
        else:
            # Everything else...
            logger = self.logger.debug

        self.logger.debug(f"{op_name if op_name is not None else '-->'} response: {response.status_code}")
        self.logger.debug(f"{op_name if op_name is not None else '-->'} cookies: {response.cookies}")
        self.logger.debug(f"{op_name if op_name is not None else '-->'} headers: {response.headers}")
        self.logger.debug(f"{url}\n{response.text}\n====")

        if op_name is not None:
            if op_name not in self.reset_list:
                local_mode = "w"
                self.reset_list.append(op_name)
            else:
                local_mode = mode
            with open(op_name + '.xml', local_mode) as f:
                f.write(f"<!-- {op_name if op_name is not None else '-->'} request:  POST {str(url)} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} response: {response.status_code} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} cookies:  {response.cookies} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} headers:  {response.headers} -->\n")
                f.write(response.text+"\n")
                if data is not None:
                    f.write(f"<!--\n")
                    f.write(f"{data}\n")
                    f.write(f"-->\n")

        if check is not None:
            check(response)

        response.raw.decode_content = True
        root = None
        try:
            root = etree.fromstring(response.text)
            # -- Set local namespace mapping from the source document
            self.namespace = root.nsmap
            # -- Preserve ETag header
            if 'ETag' in response.headers:
                root.attrib['ETag'] = response.headers['ETag']
        except Exception as e:
            # Didn't get back any valid XML...
            pass

        return root

    def delete_xml(self, url, if_match: str=None, op_name=None, mode="a", check=None):
        op_name = self.op_name if op_name is None else op_name

        self.logger.debug(f"delete_xml('{url}', {op_name})")
        headers = {'OSLC-Core-Version': '2.0',
                   'Accept': 'application/rdf+xml',
                   "Content-Type": "application/rdf+xml"}
        # -- add the If-Match ETag value as needed...
        if if_match is not None:
            headers['If-Match'] = if_match

        if self.use_cache and url in self.xml_cache:
            del self.xml_cache[url]  # remove from cache to force update

        # (Not sure stream and verify make sense on delete...)
        response = self.jazz_session.delete(url, headers=headers, stream=True, verify=False)

        if response.status_code >= 400 and response.status_code <= 499:
            # Error 4XX:
            logger = self.logger.error
        elif response.status_code >= 300 and response.status_code <= 399:
            # Warning 3XX:
            logger = self.logger.warning
        else:
            # Everything else...
            logger = self.logger.debug

        self.logger.debug(f"{op_name if op_name is not None else '-->'} response: {response.status_code}")
        self.logger.debug(f"{op_name if op_name is not None else '-->'} cookies: {response.cookies}")
        self.logger.debug(f"{op_name if op_name is not None else '-->'} headers: {response.headers}")
        self.logger.debug(f"{url}\n{response.text}\n====")

        if op_name is not None:
            if op_name not in self.reset_list:
                local_mode = "wb"
                self.reset_list.append(op_name)
            else:
                local_mode = mode
            with open(op_name + '.xml', local_mode) as f:
                f.write(f"<!-- {op_name if op_name is not None else '-->'} request:  DELETE {url} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} response: {response.status_code} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} cookies:  {response.cookies} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} headers:  {response.headers} -->\n")
                f.write(response.text+"\n")

        if check is not None:
            check(response)

        response.raw.decode_content = True
        root = None
        try:
            root = etree.fromstring(response.text)
            # -- Set local namespace mapping from the source document
            self.namespace = root.nsmap
            # -- Preserve ETag header
            if 'ETag' in response.headers:
                root.attrib['ETag'] = response.headers['ETag']
        except Exception as e:
            # Didn't get back any valid XML...
            pass

        return root

    def _add_from_xml(self, result: dict, element, tag: str=None, path: str=None, namespaces: dict=None, func=None):
        # todo: if the target already has an entry, convert to a list of entries. (Note, it might already be a list!)
        try:
            names = namespaces if namespaces is not None else self.namespace
            e = None
            e = element.xpath(path, namespaces=names)
            if e is not None and len(e) > 0:
                if func is not None:
                    e = func(e)
                if e is not None:
                    result[tag] = e
        except etree.XPathEvalError as ex:
            self.logger.debug("%s, '%s', %s", ex, path, names)
        pass

    def add_namespace(self, tag: str, definiton: str):
        self.namespace[tag] = definiton

    def login(self, server_alias: str=None, config_path: str=None) -> requests.Response:
        try:
            self.jazz_config = get_server_info(server_alias, config_path)  # possible FileNotFoundError
        except FileNotFoundError as f:
            self.log.fatal("Can't open JAZZ authentication configuration file: %s" % f)
            raise FileNotFoundError("Can't find Jazz configuration file", JAZZ_CONFIG_PATH)

        self.logger.info(f"Using Jazz server instance {self.jazz_config['host']}{self.jazz_config['instance']}")

        data = {'j_username': self.jazz_config['username'], 'j_password': self.jazz_config['password']}
        login_response = self.jazz_session.post(f"{self.jazz_config['host']}{self.jazz_config['instance']}/auth/j_security_check",
                                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                                data=urlencode(data),
                                                verify=False)
        self.logger.debug(f"Login response: {login_response.status_code}")
        self.logger.debug(f"Login cookies: {login_response.cookies}")
        return login_response

    def get_root_services(self):
        self.logger.debug(f"get_root_services()")
        if self._root_services is None:
            self._root_services = self.get_xml(f"{self.jazz_config['host']}{self.jazz_config['instance']}/rootservices")
        return self._root_services

    def get_root_services_catalogs(self):
        self.logger.debug(f"get_root_services_catalogs()")
        if self._root_services_catalogs is None:
            self._root_services_catalogs = self.get_root_services().xpath('//oslc_rm:rmServiceProviders/@rdf:resource',
                                                                          namespaces=self.namespace)
        return self._root_services_catalogs

    def get_service_provider(self, project: str=None) -> str:
        project = project if project is not None else self.jazz_config['project']
        self.logger.debug(f"get_service_provider('{project}')")
        if self._service_provider is None:
            catalog_url = self.get_root_services_catalogs()[0]
            project_xml_tree = self.get_xml(catalog_url)
            self._service_provider = project_xml_tree.xpath("//oslc:ServiceProvider[dcterms:title='"
                                                            + project + "']/./@rdf:about",
                                                            namespaces=self.namespace)[0]

        return self._service_provider

    def get_service_provider_root(self):
        self.logger.debug(f"get_service_provider_root()")
        if self._service_provider_root is None:
            self._service_provider_root = self.get_xml(self.get_service_provider())

        return self._service_provider_root

    def get_creation_factory_url(self):
        self.logger.debug(f"get_creation_factory()")
        if self._creation_factory is None:
            creation_factory = "//oslc:creation/@rdf:resource"
            self._creation_factory = self.get_service_provider_root().xpath(creation_factory, namespaces=self.namespace)[0]

        return self._creation_factory

    def get_query_base(self):
        if self._query_base is None:
            query_capability = "//oslc:QueryCapability[dcterms:title=\"Query Capability\"]/oslc:queryBase/@rdf:resource"
            self._query_base = self.get_service_provider_root().xpath(query_capability, namespaces=self.namespace)[0]

        return self._query_base

    def get_requirement_factory(self, resource_type: str="http://open-services.net/ns/rm#Requirement") -> str:
        self.logger.debug(f"get_create_factory()")
        if resource_type not in self._requirement_factory:
            requirement_factory_xpath = f'//oslc:CreationFactory/oslc:resourceType[@rdf:resource="{resource_type}"]/../oslc:creation/@rdf:resource'
            self._requirement_factory[resource_type] = self.get_service_provider_root().xpath(requirement_factory_xpath,
                                                                                              namespaces=Jazz.xpath_namespace())[0]
        return self._requirement_factory[resource_type]

    def get_shapes_nodes(self, resource_type: str="http://open-services.net/ns/rm#Requirement"):
        self.logger.debug("Getting shapes info...")
        if resource_type not in self._shapes_nodes_root:
            requirement_factory_shapes_xpath = f'//oslc:CreationFactory/oslc:resourceType[@rdf:resource="{resource_type}"]/../oslc:resourceShape/@rdf:resource'
            requirement_factory_shapes = self.get_service_provider_root().xpath(requirement_factory_shapes_xpath,
                                                                                namespaces=Jazz.xpath_namespace())
            self._shapes_nodes_root[resource_type] = {
                resource_shape.xpath("//oslc:ResourceShape/dcterms:title/text()",
                                     namespaces=Jazz.xpath_namespace())[0]: resource_shape
                for resource_shape in
                [self.get_xml(shape) for shape in requirement_factory_shapes]
            }

        return self._shapes_nodes_root[resource_type]

    def get_shape_node_root(self, shape_type: str="", resource_type: str="http://open-services.net/ns/rm#Requirement"):
        shape_nodes = self.get_shapes_nodes(resource_type)
        if shape_type in shape_nodes:
            shape_node = shape_nodes[shape_type]
        else:
            raise Exception(f"Did not find {shape_type} in defined shape nodes for {resource_type}")

        return shape_node

    def get_shape_url(self, shape_type: str="", resource_type: str="http://open-services.net/ns/rm#Requirement"):
        shape_nodes = self.get_shapes_nodes(resource_type)
        if shape_type in shape_nodes:
            shape_uri = shape_nodes[shape_type].xpath("//oslc:ResourceShape/@rdf:about", namespaces=Jazz.xpath_namespace())[0]
        else:
            raise Exception(f"Did not find {shape_type} in defined shapes for {resource_type}")

        return shape_uri

    # -----------------------------------------------------------------------------------------------------------------

    def query_xml(self, oslc_prefix=None, oslc_select=None, oslc_where=None, op_name=None):
        query = self.get_query_base()
        prefix = oslc_prefix if oslc_prefix is not None \
                    else ",".join([f'{key}=<{link}>' for key, link in self.namespace.items()])

        prefix = "&"+urlencode({'oslc.prefix': prefix})
        select = "&"+urlencode({'oslc.select': oslc_select}) if oslc_select is not None else ""
        where = "&"+urlencode({'oslc.where': oslc_where}) if oslc_where is not None else ""
        query_text = f"{query}{prefix}{select}{where}"
        query_root = self.get_xml(query_text, op_name=op_name)
        return query_root

    def query(self, oslc_prefix=None, oslc_select=None, oslc_where=None, op_name=None):
        query_root = self.query_xml(oslc_prefix=oslc_prefix, oslc_select=oslc_select, oslc_where=oslc_where, op_name=op_name)
        query_result = {'query_root': query_root, 'query_result': etree.tostring(query_root)}
        self._add_from_xml(query_result, query_root, 'result', './oslc:ResponseInfo/dcterms:title', func=Jazz._get_text)
        self._add_from_xml(query_result, query_root, 'about', './rdf:Description/@rdf:about', func=Jazz._get_first)
        self._add_from_xml(query_result, query_root, 'RequirementCollections', '//oslc_rm:RequirementCollection/@rdf:about')
        self._add_from_xml(query_result, query_root, 'Requirements', '//oslc_rm:Requirement/@rdf:about')
        return query_result

    def _get_resources(self, resource_list, op_name=None):
        return [self.get_xml(resource_url, op_name=op_name, mode="a+") for resource_url in resource_list]


    def read(self, resource_url, op_name=None):
        root_element = self.get_xml(resource_url, op_name=op_name, mode="a+")
        this_item = {'Root': root_element, 'resource_url': resource_url}
        self._add_from_xml(this_item, root_element, 'about', './rdf:Description/@rdf:about')
        self._add_from_xml(this_item, root_element, 'modified', './rdf:Description/dcterms:modified', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'description', './rdf:Description/dcterms:description', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'creator', './rdf:Description/dcterms:creator/@rdf:about')
        self._add_from_xml(this_item, root_element, 'created', './rdf:Description/dcterms:created', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'ServiceProvider', './rdf:Description/oslc:serviceProvider/@rdf:resource', func=self._get_resources)
        self._add_from_xml(this_item, root_element, 'access_control', './rdf:Description/acp:accessContro/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'primary_text', './rdf:Description/jazz_rm:primaryText')
        self._add_from_xml(this_item, root_element, 'type', './rdf:Description/rdf:type/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'contributor', './rdf:Description/dcterms:contributor/@rdf:resource', func=self._get_resources)
        self._add_from_xml(this_item, root_element, 'projectArea', './rdf:Description/process:projectArea/@rdf:resource', func=self._get_resources)
        self._add_from_xml(this_item, root_element, 'component', './rdf:Description/oslc_config:component/@rdf:resource', func=self._get_resources)
        self._add_from_xml(this_item, root_element, 'identifier', './rdf:Description/dcterms:identifier', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'title', './rdf:Description/dcterms:title', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'parent', './rdf:Description/nav:parent/@rdf:resource', func=self._get_resources)
        self._add_from_xml(this_item, root_element, 'instanceShape', './rdf:Description/oslc:instanceShape/@rdf:resource')
        # -- Entry below should be for a collection...
        self._add_from_xml(this_item, root_element, 'uses', '//oslc_rm:uses/@rdf:resource')
        # todo: This looks like a special form and should be handled as such...
        self._add_from_xml(this_item, root_element, 'rm_property', './rdf:Description/rm_property:*/@rdf:resource', func=self._get_resources)
        # self._add_from_xml(this_item, root_element, 'rm_property:_4G6Ioa_4EeekDP1y4xXYPQ', './rdf:Description/rm_property:_4G6Ioa_4EeekDP1y4xXYPQ/@rdf:resource', func=self._get_resources)
        self.logger.debug(this_item)
        return this_item

    shape_cache = {}
    shape_to_class_mapping = {}

    @classmethod
    def map_shape_name_to_class(cls, name: str, shape_class: type):
        cls.shape_to_class_mapping[name] = shape_class

    def get_shape_info(self, shape_uri: str) -> {}:
        if shape_uri not in self.shape_cache:
            shape_xml = self.get_xml(shape_uri)
            shape_name = shape_xml.xpath("//oslc:ResourceShape/dcterms:title/text()",
                                         namespaces=self.xpath_namespace())[0]
            if shape_name not in self.shape_to_class_mapping:
                log.logger.warning(f"No class mapping found for '{shape_name}'")

            self.shape_cache[shape_uri] = {
                'xml': shape_xml,
                'name': shape_name,
                'class': self.shape_to_class_mapping[shape_name] if shape_name in self.shape_to_class_mapping else None
            }
        return self.shape_cache[shape_uri]

    def get_object_from_uri(self, uri_list, op_name=None):
        """Return an instance of the class refered to by the XML at the uri"""
        if not isinstance(uri_list, set) and not isinstance(uri_list, list):
            uri_list = [uri_list]

        artifacts = set()
        for uri in uri_list:
            artifact_xml_root = self.get_xml(url=uri, op_name=op_name if op_name is not None else self.op_name)
            # -- If you don't find instance shape, resort to the item type name (e.g., 'folder')
            if artifact_xml_root.xpath("//nav:folder", namespaces=Jazz.xpath_namespace()):
                artifacts.add(self.shape_to_class_mapping['folder'](self, xml_root=artifact_xml_root))
            else:
                shape_uri = artifact_xml_root.xpath("//oslc:instanceShape/@rdf:resource", namespaces=Jazz.xpath_namespace())[0]
                shape_info = self.get_shape_info(shape_uri)
                if shape_info['class'] is not None:
                    artifacts.add(shape_info['class'](self, instance_shape=shape_uri, xml_root=artifact_xml_root))
                else:
                    self.logger.warning(f"Unknown Shape, Info is: {shape_info}")
                    from jazz_dng_client.artifacts import GenericRequirement
                    artifacts.add(GenericRequirement(self, instance_shape=shape_uri, xml_root=artifact_xml_root))

        return artifacts


def main():
    j = Jazz(server_alias="sandbox", config_path=JAZZ_CONFIG_PATH, op_name=XML_LOG_FILE)
    query_result = j.query(oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
                           oslc_select='*',         # 'dcterms:identifier',
                           oslc_where='dcterms:identifier=67383'
                           )
    
    # import xmltodict


    if 'Requirements' in query_result:
        # Note: even if the select above limits the returned fields, the read below will read the entire item!
        requirements = {item['identifier']: item for item in [member for member in query_result['Requirements'][:2]]}
        log.logger.info("\n\n%d items in requirements", len(requirements))
        p = pd.DataFrame(requirements)
        log.logger.info(p)

    if 'RequirementCollections' in query_result:
        collections = {item['identifier']: item for item in [j.read(member) for member in query_result['RequirementCollections'][:2]]}
        log.logger.info("\n\n%d Requirement Collections", len(collections))
        q = pd.DataFrame(collections)
        log.logger.info(q)

    pass


if __name__ == '__main__':
    main()
