import urllib3
import requests
import lxml as etree
from yaml import dump
from json import dumps
import pandas as pd

# -- Support
import sys
from os.path import pathsep, dirname, realpath
from utility_funcs.search import get_server_info
import utility_funcs.logger_yaml as log

from lxml import etree

urllib3.disable_warnings()

# -- Set up logger...
LOG_CONFIG_FILE = 'logging.yaml'+pathsep+dirname(realpath(sys.argv[0]))+'/logging.yaml'
log.setup_logging("logging.yaml", override={'handlers': {'info_file_handler': {'filename': 'audit_jama_jira_matchup.log'}}})
log.logger.setLevel(log.logging.getLevelName("INFO"))
log.logger.disabled = False

JAZZ_CONFIG_PATH = f"{dirname(realpath(sys.argv[0]))}/config.yaml{pathsep}~/.jazz/config.yaml"

class Jazz(requests.Session):

    def _get_text(x):
        return x[0].text if len(x) > 0 else ""

    def _get_first(x):
        return x[0] if len(x) > 0 else None

    def _get_xml(self, url, op_name="", mode="w"):
        response = self.get(url,
                            headers={'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml'},
                            stream=True, verify=False)
        self.logger.debug(f"{op_name} response: {response.status_code}")
        self.logger.debug(f"{op_name} cookies: {response.cookies}")
        self.logger.debug(f"{op_name} headers: {response.headers}")
        self.logger.debug(f"{url}\n{response.text}\n====")
        if op_name:
            if op_name not in self.reset_list:
                local_mode = "w"
                self.reset_list.append(op_name)
            else:
                local_mode = mode
            with open(op_name + '.xml', local_mode) as f:
                f.write(response.text)

        response.raw.decode_content = True
        root = etree.fromstring(response.text)
        # -- Set local namespace mapping from the source document
        self.namespace = root.nsmap
        # -- Preserve ETag header
        if 'ETag' in response.headers:
            root.attrib['ETag'] = response.headers['ETag']
        return root

    def _add_from_xml(self, result: dict, element, tag: str=None, path: str=None, namespaces: dict=None, func=None):
        # todo: if the target already has an entry, convert to a list of entries. (Note, it might already be a list!)
        try:
            e = None
            e = element.xpath(path, namespaces=namespaces if namespaces is not None else self.namespace)
            if e is not None and len(e) > 0:
                if func is not None:
                    e = func(e)
                if e is not None:
                    result[tag] = e
        except etree.XPathEvalError as ex:
            self.logger.debug(ex)
        pass

    def __init__(self, server_alias=None, config_path=None, namespace=None, log=log):
        requests.Session.__init__(self)
        self.RootServices = {}
        self.logger = log.logger
        self.namespace = namespace
        self.reset_list = []

        try:
            jazz_config = get_server_info(server_alias, config_path)  # possible FileNotFoundError
        except FileNotFoundError as f:
            self.log.fatal("Can't open JAZZ authentication configuration file: %s" % f)
            raise FileNotFoundError("Can't find Jazz configuration file", JAZZ_CONFIG_PATH)

        self.logger.info(f"Using JAMA server instance {jazz_config['host']}{jazz_config['instance']}")

        login_response = self.post(f"{jazz_config['host']}{jazz_config['instance']}/auth/j_security_check",
                                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                                   data=f"j_username={jazz_config['username']}&j_password={jazz_config['password']}",
                                   verify=False)
        self.logger.debug(f"Login response: {login_response.status_code}")
        self.logger.debug(f"Login cookies: {login_response.cookies}")
        # print(f"{login_response.text}\n=========================")

        pa_root_services = self._get_xml(f"{jazz_config['host']}{jazz_config['instance']}/rootservices", "Root Services")
        root_services_catalogs = pa_root_services.xpath('//oslc_rm:rmServiceProviders/@rdf:resource',
                                                        namespaces=self.namespace)
        self.RootServices['catalogs'] = []
        for catalog_url in root_services_catalogs:
            catalog = {'url': catalog_url, 'projects': {}}
            self.RootServices['catalogs'].append(catalog)
            self.logger.debug("Catalog URL is: %s", self.RootServices)

            # -- "ServiceProvider" are services related to a particular project...
            project_xml_tree = self._get_xml(catalog['url'], "Project Catalog")
            project_catalog = project_xml_tree.xpath('.//oslc:ServiceProvider', namespaces=self.namespace)
            for project in project_catalog:

                def get_text(x): return x[0].text if len(x)>0 else ""

                def get_first(x): return x[0] if len(x)>0 else None

                project_info = {'services': {}}
                self._add_from_xml(project_info, project, 'ServiceProvider', '../oslc:ServiceProvider/@rdf:about', func=Jazz._get_first)
                self._add_from_xml(project_info, project, 'ConsumerRegistry', './jp:consumerRegistry/@rdf:resource', func=Jazz._get_first)
                self._add_from_xml(project_info, project, 'title', './dcterms:title', func=get_text)
                self._add_from_xml(project_info, project, 'services_url', '//oslc:ServiceProvider/@rdf:about', func=Jazz._get_first)
                self._add_from_xml(project_info, project, 'registry', './jp:consumerRegistry/@rdf:resource', func=Jazz._get_first)
                self._add_from_xml(project_info, project, 'details', './oslc:details//@rdf:resource', func=Jazz._get_first)
                self._add_from_xml(project_info, project, 'description', './dcterms:description', func=Jazz._get_text)
                catalog['projects'][project_info['title']] = project_info

                # -- List of services related to a particular project
                pa_services = self._get_xml(project_info['ServiceProvider'], project_info['title'] + " Project Services")
                # note: The problem here is that within a service section there are multiple (service) items...
                services = pa_services.xpath('.//oslc:Service/*', namespaces=self.namespace)
                for service in services:
                    service_info = {}
                    self._add_from_xml(service_info, service, 'title', './*/dcterms:title', func=Jazz._get_text)
                    self._add_from_xml(service_info, service, 'hintHeight', './*/oslc:hintHeight', func=Jazz._get_text)
                    self._add_from_xml(service_info, service, 'hintWidth', './*/oslc:hintWidth', func=Jazz._get_text)
                    self._add_from_xml(service_info, service, 'label', './*/oslc:label', func=Jazz._get_text)
                    self._add_from_xml(service_info, service, 'provider', './*/oslc:ServiceProvider/@rdf:about', func=Jazz._get_first)
                    self._add_from_xml(service_info, service, 'registry', './*/jp:consumerRegistry/@rdf:resource', func=Jazz._get_first)
                    self._add_from_xml(service_info, service, 'details', './*/oslc:details/@rdf:resource', func=Jazz._get_first)
                    self._add_from_xml(service_info, service, 'dialog', './*/oslc:dialog/@rdf:resource', func=Jazz._get_first)
                    self._add_from_xml(service_info, service, 'usage', './*/oslc:usage/@rdf:resource', func=None)
                    self._add_from_xml(service_info, service, 'resourceType', './*/oslc:resourceType/@rdf:resource', func=Jazz._get_first)
                    self._add_from_xml(service_info, service, 'creation', './*/oslc:creation/@rdf:resource', func=Jazz._get_first)
                    self._add_from_xml(service_info, service, 'queryBase', './*/oslc:queryBase/@rdf:resource', func=Jazz._get_first)
                    # Note: the misspelling of filter as "filerBase" in the XPATH!
                    self._add_from_xml(service_info, service, 'filterBase', './*/oslc:filerBase/@rdf:resource', func=Jazz._get_first)
                    self._add_from_xml(service_info, service, 'filterBase', './*/oslc:filterBase/@rdf:resource', func=Jazz._get_first)
                    # -- Always a list!
                    self._add_from_xml(service_info, service, 'resourceShape', './*/oslc:resourceShape/@rdf:resource', func=None)
                    self._add_from_xml(service_info, service, 'component', './*/oslc_config:component/@rdf:resource', func=Jazz._get_first)

                    if 'title' not in service_info:
                        # Actually, everything is empty... Maybe you should print it and see what it is...
                        # Note: this seems to catch a domain entry at the same level as the names service, groupped
                        # Note: under a service tag... Implies that there's something I don't understand. :-)
                        self.logger.debug("Could not find name of service: %s", etree.tostring(service, pretty_print=True))
                        continue
                    if len(service_info)<3:
                        # Most servcies have 3 or more entries...
                        self.logger.debug("Only partially decoded service: %s", etree.tostring(service, pretty_print=True))

                    project_info['services'][service_info['title']] = service_info

    def query_all(self):
        query_section = self.RootServices['catalogs'][0]['projects']['SSG-OTC Product Management - DNG']['services']['Query Capability']
        query = query_section['queryBase']
        query_root = self._get_xml(query, "Query")
        query_result = {}
        self._add_from_xml(query_result, query_root, 'result', './oslc:ResponseInfo/dcterms:title', func=Jazz._get_text)
        self._add_from_xml(query_result, query_root, 'about', './rdf:Description/@rdf:about', func=Jazz._get_first)
        self._add_from_xml(query_result, query_root, 'RequirementCollections', '//oslc_rm:RequirementCollection/@rdf:about')
        self._add_from_xml(query_result, query_root, 'Requirements', '//oslc_rm:Requirement/@rdf:about')
        return query_result

    def read(self, resource_url):
        root_element = self._get_xml(resource_url, "item", mode="a+")
        this_item = {'Root': root_element}
        self._add_from_xml(this_item, root_element, 'about', './rdf:Description/@rdf:about')
        self._add_from_xml(this_item, root_element, 'modified', './rdf:Description/dcterms:modified', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'description', './rdf:Description/dcterms:description', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'creator', './rdf:Description/dcterms:creator/@rdf:about')
        self._add_from_xml(this_item, root_element, 'created', './rdf:Description/dcterms:created', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'ServiceProvider', './rdf:Description/oslc:serviceProvider/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'access_control', './rdf:Description/acp:accessContro/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'primary_text', './rdf:Description/jazz_rm:primaryText')
        self._add_from_xml(this_item, root_element, 'type', './rdf:Description/rdf:type/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'contributor', './rdf:Description/dcterms:contributor/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'projectArea', './rdf:Description/process:projectArea/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'component', './rdf:Description/oslc_config:component/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'identifier', './rdf:Description/dcterms:identifier', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'title', './rdf:Description/dcterms:title', func=Jazz._get_text)
        self._add_from_xml(this_item, root_element, 'parent', './rdf:Description/nav:parent/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'instanceShape', './rdf:Description/oslc:instanceShape/@rdf:resource')
        # -- Entry below should be for a collection...
        self._add_from_xml(this_item, root_element, 'uses', '//oslc_rm:uses/@rdf:resource')
        # todo: This looks like a special form and should be handled as such...
        self._add_from_xml(this_item, root_element, 'rm_property:_5LMQKK_4EeekDP1y4xXYPQ', './rdf:Description/rm_property:_5LMQKK_4EeekDP1y4xXYPQ/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'rm_property:_4G6Ioa_4EeekDP1y4xXYPQ', './rdf:Description/rm_property:_4G6Ioa_4EeekDP1y4xXYPQ/@rdf:resource')
        self.logger.debug(this_item)
        return this_item


def main():
    j = Jazz(server_alias="dng", config_path=JAZZ_CONFIG_PATH)
    query_result = j.query_all()
    requirements = {item['identifier']: item for item in [j.read(member) for member in query_result['Requirements'][:2]]}
    collections = {item['identifier']: item for item in [j.read(member) for member in query_result['RequirementCollections'][:2]]}

    p = pd.DataFrame(requirements)
    q = pd.DataFrame(collections)

    log.logger.info(p)
    log.logger.info(q)

    pass


if __name__ == '__main__':
    main()
