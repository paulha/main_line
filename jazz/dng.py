# -- Support
import sys
from os.path import pathsep, dirname, realpath

#import lxml as etree
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

    
    def __init__(self, server_alias=None, config_path=None, namespace=None, op_name=XML_LOG_FILE, log=log):
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
        self._query_base = None
        self._requirement_factory = {}
        self._shapes_nodes_root = {}

        self.logger.info("Start initialization")

        login_response = self.login(server_alias, config_path)

        root_services_catalogs = self.get_root_services_catalogs()
        self.logger.info("Initialization completed")

    def _get_text(x):
        return x[0].text if len(x) > 0 else ""

    def _get_first(x):
        return x[0] if len(x) > 0 else None

    def _get_xml(self, url, op_name=None, mode="a"):
        op_name = self.op_name if op_name is None else op_name

        self.logger.info(f"_get_xml('{url}', {op_name})")
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

        logger(f"{op_name if op_name is not None else '-->'} response: {response.status_code}")
        logger(f"{op_name if op_name is not None else '-->'} cookies: {response.cookies}")
        logger(f"{op_name if op_name is not None else '-->'} headers: {response.headers}")
        logger(f"{url}\n{response.text}\n====")

        if op_name is not None:
            if op_name not in self.reset_list:
                local_mode = "w"
                self.reset_list.append(op_name)
            else:
                local_mode = mode
            with open(op_name + '.xml', local_mode) as f:
                f.write(f"<!-- {op_name} request:  GET {url} -->\n")
                f.write(f"<!-- {op_name} response: {response.status_code} -->\n")
                f.write(f"<!-- {op_name} cookies:  {response.cookies} -->\n")
                f.write(f"<!-- {op_name} headers:  {response.headers} -->\n")
                f.write(response.text+"\n")

        response.raw.decode_content = True
        root = etree.fromstring(response.text)
        # -- Set local namespace mapping from the source document
        self.namespace = root.nsmap
        # -- Preserve ETag header
        if 'ETag' in response.headers:
            root.attrib['ETag'] = response.headers['ETag']

        return root

    def _post_xml(self, url, data=None, json=None, if_match: str=None, op_name=None, mode="a"):
        op_name = self.op_name if op_name is None else op_name

        self.logger.info(f"_post_xml('{url}', {op_name})")
        headers = {'OSLC-Core-Version': '2.0',
                   'Accept': 'application/rdf+xml',
                   "Content-Type": "application/rdf+xml"}
        # -- add the If-Match ETag value as needed...
        if if_match is not None:
            headers['If-Match'] = if_match

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

        logger(f"{op_name if op_name is not None else '-->'} response: {response.status_code}")
        logger(f"{op_name if op_name is not None else '-->'} cookies: {response.cookies}")
        logger(f"{op_name if op_name is not None else '-->'} headers: {response.headers}")
        logger(f"{url}\n{response.text}\n====")

        if op_name is not None:
            if op_name not in self.reset_list:
                local_mode = "w"
                self.reset_list.append(op_name)
            else:
                local_mode = mode
            with open(op_name + '.xml', local_mode) as f:
                f.write(f"<!-- {op_name if op_name is not None else '-->'} request:  POST {url} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} response: {response.status_code} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} cookies:  {response.cookies} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} headers:  {response.headers} -->\n")
                f.write(response.text+"\n")
                if data is not None or json is not None:
                    f.write(f"<!--\n")
                    f.write(f"{data if data is not None else json}\n")
                    f.write(f"-->\n")

        return response

    def _put_xml(self, url, data=None, if_match: str=None, op_name=None, mode="a"):
        op_name = self.op_name if op_name is None else op_name

        self.logger.info(f"_put_xml('{url}', {op_name})")
        headers = {'OSLC-Core-Version': '2.0',
                   'Accept': 'application/rdf+xml',
                   "Content-Type": "application/rdf+xml"}
        # -- add the If-Match ETag value as needed...
        if if_match is not None:
            headers['If-Match'] = if_match

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

        logger(f"{op_name if op_name is not None else '-->'} response: {response.status_code}")
        logger(f"{op_name if op_name is not None else '-->'} cookies: {response.cookies}")
        logger(f"{op_name if op_name is not None else '-->'} headers: {response.headers}")
        logger(f"{url}\n{response.text}\n====")

        if op_name is not None:
            if op_name not in self.reset_list:
                local_mode = "w"
                self.reset_list.append(op_name)
            else:
                local_mode = mode
            with open(op_name + '.xml', local_mode) as f:
                f.write(f"<!-- {op_name if op_name is not None else '-->'} request:  POST {url} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} response: {response.status_code} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} cookies:  {response.cookies} -->\n")
                f.write(f"<!-- {op_name if op_name is not None else '-->'} headers:  {response.headers} -->\n")
                f.write(response.text+"\n")
                if data is not None:
                    f.write(f"<!--\n")
                    f.write(f"{data}\n")
                    f.write(f"-->\n")

        return response

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

        self.logger.info(f"Using JAMA server instance {self.jazz_config['host']}{self.jazz_config['instance']}")

        login_response = self.jazz_session.post(f"{self.jazz_config['host']}{self.jazz_config['instance']}/auth/j_security_check",
                                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                                data=f"j_username={self.jazz_config['username']}&j_password={self.jazz_config['password']}",
                                                verify=False)
        self.logger.debug(f"Login response: {login_response.status_code}")
        self.logger.debug(f"Login cookies: {login_response.cookies}")
        return login_response

    def get_root_services(self):
        self.logger.info(f"get_root_services()")
        if self._root_services is None:
            self._root_services = self._get_xml(f"{self.jazz_config['host']}{self.jazz_config['instance']}/rootservices",
                                                XML_LOG_FILE)
        return self._root_services

    def get_root_services_catalogs(self):
        self.logger.info(f"get_root_services_catalogs()")
        if self._root_services_catalogs is None:
            self._root_services_catalogs = self.get_root_services().xpath('//oslc_rm:rmServiceProviders/@rdf:resource',
                                                                          namespaces=self.namespace)
        return self._root_services_catalogs

    def get_service_provider(self, project: str=None) -> str:
        project = project if project is not None else self.jazz_config['project']
        self.logger.info(f"get_service_provider('{project}')")
        if self._service_provider is None:
            catalog_url = self.get_root_services_catalogs()[0]
            project_xml_tree = self._get_xml(catalog_url, XML_LOG_FILE)
            self._service_provider = project_xml_tree.xpath("//oslc:ServiceProvider[dcterms:title='"
                                                            + project + "']/./@rdf:about",
                                                            namespaces=self.namespace)[0]

        return self._service_provider

    def get_service_provider_root(self):
        self.logger.info(f"get_service_provider_root()")
        if self._service_provider_root is None:
            self._service_provider_root = self._get_xml(self.get_service_provider(), op_name='service provider')

        return self._service_provider_root

    def get_query_base(self):
        if self._query_base is None:
            query_capability = "//oslc:QueryCapability[dcterms:title=\"Query Capability\"]/oslc:queryBase/@rdf:resource"
            self._query_base = self.get_service_provider_root().xpath(query_capability, namespaces=self.namespace)[0]

        return self._query_base

    def discover_root_folder(self, op_name=None):
        folder_query_xpath = '//oslc:QueryCapability[dcterms:title="Folder Query Capability"]/oslc:queryBase/@rdf:resource'
        folder_query_uri = self.get_service_provider_root().xpath(folder_query_xpath, namespaces=Jazz.xpath_namespace())[0]

        folder_result_xml = self._get_xml(folder_query_uri, op_name=op_name)

        root_folder_xpath = "//nav:folder[dcterms:title=\"root\"]/@rdf:about"
        root_path_uri = folder_result_xml.xpath(root_folder_xpath, namespaces=Jazz.xpath_namespace())[0]

        return root_path_uri

    def create_folder(self, folder_name: str=None, parent_folder: str=None) -> str:
        self.logger.info(f"create_folder('{folder_name}')")

        service_provider_url = self.get_service_provider()

        # Get the Project ID String
        project_id= re.split('/', service_provider_url)[-2]

        if folder_name is None:
            folder_name = "OSLC Created";

        if parent_folder is None:
            parent_folder = self.discover_root_folder()

        target_project = "?projectURL=" + self.jazz_config['host'] + self.jazz_config['instance'] + "/process/project-areas/" + project_id
        folder_creation_factory = self.jazz_config['host'] + self.jazz_config['instance'] + "/folders" + target_project;

        xml = f'''
            <rdf:RDF
                    xmlns:nav="http://jazz.net/ns/rm/navigation#" 
                    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                    xmlns:oslc_rm="http://open-services.net/ns/rm#"
                    xmlns:oslc="http://open-services.net/ns/core#"
                    xmlns:rmTypes="http://www.ibm.com/xmlns/rdm/types/"
                    xmlns:dcterms="http://purl.org/dc/terms/"
                    xmlns:rm="http://jazz.net/ns/rm#">
                <rdf:Description rdf:nodeID="A0">
                    <rdf:type rdf:resource="http://jazz.net/ns/rm/navigation#folder"/>
                    <dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">{folder_name}</dcterms:title>
                    <nav:parent rdf:resource="{parent_folder}"/>
                </rdf:Description>
            </rdf:RDF>
        '''
        response = self._post_xml(folder_creation_factory, op_name=XML_LOG_FILE, data=xml)
        return response.headers['location']

    def delete_folder(self, folder: str):
        raise Exception("Not Yet Implemented")

    def get_requirement_factory(self, resource_type: str="http://open-services.net/ns/rm#Requirement") -> str:
        self.logger.info(f"get_create_factory()")
        if resource_type not in self._requirement_factory:
            requirement_factory_xpath = f'//oslc:CreationFactory/oslc:resourceType[@rdf:resource="{resource_type}"]/../oslc:creation/@rdf:resource'
            self._requirement_factory[resource_type] = self.get_service_provider_root().xpath(requirement_factory_xpath,
                                                                                              namespaces=Jazz.xpath_namespace())[0]
        return self._requirement_factory[resource_type]

    def get_shapes_nodes(self, resource_type: str="http://open-services.net/ns/rm#Requirement"):
        self.logger.info("Getting shapes info...")
        if resource_type not in self._shapes_nodes_root:
            requirement_factory_shapes_xpath = f'//oslc:CreationFactory/oslc:resourceType[@rdf:resource="{resource_type}"]/../oslc:resourceShape/@rdf:resource'
            requirement_factory_shapes = self.get_service_provider_root().xpath(requirement_factory_shapes_xpath,
                                                                                namespaces=Jazz.xpath_namespace())
            self._shapes_nodes_root[resource_type] = {
                resource_shape.xpath("//oslc:ResourceShape/dcterms:title/text()",
                                     namespaces=Jazz.xpath_namespace())[0]: resource_shape
                for resource_shape in
                [self._get_xml(shape, op_name='shapes') for shape in requirement_factory_shapes]
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

    def create_requirement(self, parent_folder_URI: str=None,
                           resource_type: str="http://open-services.net/ns/rm#Requirement",
                           op_name: str=None):
        self.logger.info(f"create_requirement('{parent_folder_URI}')")
        factory_root = self.get_service_provider_root()
        resource_shapes_roots = self.get_shapes_nodes(resource_type=resource_type)
        uri = self.get_shape_url(shape_type=self.jazz_config['requirement_shape'])
        requirement_root = self._get_xml(uri, op_name=op_name)
        shape_text = etree.tostring(self.get_shape_node_root(shape_type=self.jazz_config['requirement_shape'], resource_type=resource_type))
        names = [value for value in self.get_shape_node_root(shape_type=self.jazz_config['requirement_shape'], resource_type=resource_type)
                  .xpath('//oslc:name/text()', namespaces=Jazz.xpath_namespace())]
        pass


    def get_folder_name(self, folder: str, op_name=None) -> str:
        folder_xml = self._get_xml(folder, op_name=op_name)
        node = folder_xml.xpath("//dcterms:title/text()", namespaces=Jazz.xpath_namespace())
        return node[0]

    # -----------------------------------------------------------------------------------------------------------------

    def query(self, oslc_prefix=None, oslc_select=None, oslc_where=None, op_name=None):
        query = self.get_query_base()
        prefix = oslc_prefix if oslc_prefix is not None \
                    else ",".join([f'{key}=<{link}>' for key, link in self.namespace.items()])

        prefix = "&"+urlencode({'oslc.prefix': prefix})
        select = "&"+urlencode({'oslc.select': oslc_select}) if oslc_select is not None else ""
        where = "&"+urlencode({'oslc.where': oslc_where}) if oslc_where is not None else ""
        query_text = f"{query}{prefix}{select}{where}"
        query_root = self._get_xml(query_text, op_name=op_name)
        # -- Does it really make sense to do this:? Might make more sense to return the xml document 'query_root'...
        query_result = {'query_text': query_text, 'query_root': query_root, 'query_result': etree.tostring(query_root)}
        self._add_from_xml(query_result, query_root, 'result', './oslc:ResponseInfo/dcterms:title', func=Jazz._get_text)
        self._add_from_xml(query_result, query_root, 'about', './rdf:Description/@rdf:about', func=Jazz._get_first)
        self._add_from_xml(query_result, query_root, 'RequirementCollections', '//oslc_rm:RequirementCollection/@rdf:about')
        self._add_from_xml(query_result, query_root, 'Requirements', '//oslc_rm:Requirement/@rdf:about')
        return query_result

    def _get_resources(self, resource_list, op_name=None):
        return [self._get_xml(resource_url, op_name=op_name, mode="a+") for resource_url in resource_list]


    def read(self, resource_url, op_name=None):
        root_element = self._get_xml(resource_url, op_name=op_name, mode="a+")
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