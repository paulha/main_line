import requests
from yaml import dump
from json import dumps

# -- Support
import sys
from os.path import pathsep, dirname, realpath
from utility_funcs.search import get_server_info
import utility_funcs.logger_yaml as log

from lxml import etree

# -- Set up logger...
LOG_CONFIG_FILE = 'logging.yaml'+pathsep+dirname(realpath(sys.argv[0]))+'/logging.yaml'
log.setup_logging("logging.yaml", override={'handlers': {'info_file_handler': {'filename': 'audit_jama_jira_matchup.log'}}})
log.logger.setLevel(log.logging.getLevelName("INFO"))
log.logger.disabled = False

JAZZ_CONFIG_PATH = f"{dirname(realpath(sys.argv[0]))}/config.yaml{pathsep}~/.jazz/config.yaml"

olsc_namespaces = {
    'dc': 'http://purl.org/dc/terms/',
    'calm': "http://jazz.net/xmlns/prod/jazz/calm/1.0/",
    # 'jfs_proc' : 'http://jazz.net/xmlns/prod/jazz/process/1.0/',
    # 'oslc_disc': 'http://open-services.net/xmlns/discovery/1.0/',
    'oslc_rm': "http://open-services.net/xmlns/rm/1.0/",
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'oslc': 'http://open-services.net/ns/core#',
    'dcterms': "http://purl.org/dc/terms/",
    'jp': "http://jazz.net/xmlns/prod/jazz/process/1.0/",
}

class Jazz(requests.Session):

    def _get_xml(self, url, op_name=""):
        response = self.get(url,
                            headers={'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml'},
                            stream=True, verify=False)
        self.logger.debug(f"{op_name} response: {response.status_code}")
        self.logger.debug(f"{op_name} cookies: {response.cookies}")
        self.logger.debug(f"{url}\n{response.text}\n====")
        if op_name:
            with open(op_name + '.xml', 'w') as f:
                f.write(response.text)

        response.raw.decode_content = True
        return etree.fromstring(response.text)

    def _add_from_xml(self, result: dict, element, tag: str=None, path: str=None, namespaces: dict=None, func=None):
        # todo: if the target already has an entry, convert to a list of entries. (Note, it might already be a list!)
        # note: that this is going to return a list of elements if there's more than one there...
        e = element.xpath(path, namespaces=namespaces if namespaces is not None else self.namespace)
        if func is not None:
            e = func(e)
        if e is not None:
            result[tag] = e
        pass

    def __init__(self, server_alias=None, config_path=None, namespace=None, log=log):
        requests.Session.__init__(self)
        self.RootServices = {}
        self.logger = log.logger
        self.namespace = namespace

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
        self.logger.info(f"Login response: {login_response.status_code}")
        self.logger.info(f"Login cookies: {login_response.cookies}")
        # print(f"{login_response.text}\n=========================")

        pa_root_services = self._get_xml(f"{jazz_config['host']}{jazz_config['instance']}/rootservices", "Root Services")
        root_services_catalogs = pa_root_services.xpath('//oslc_rm:rmServiceProviders/@rdf:resource',
                                                        namespaces=olsc_namespaces)
        self.RootServices['catalogs'] = []
        for catalog_url in root_services_catalogs:
            catalog = {'url': catalog_url, 'projects': {}}
            self.RootServices['catalogs'].append(catalog)
            self.logger.info("Catalog URL is: %s", self.RootServices)

            # -- "ServiceProvider" are services related to a particular project...
            project_xml_tree = self._get_xml(catalog['url'], "Project Catalog")
            project_catalog = project_xml_tree.xpath('.//oslc:ServiceProvider', namespaces=self.namespace)
            for project in project_catalog:

                def get_text(x): return x[0].text if len(x)>0 else ""

                def get_first(x): return x[0] if len(x)>0 else None

                project_info = {'services': {}}
                self._add_from_xml(project_info, project, 'title', './/dcterms:title', func=get_text)
                self._add_from_xml(project_info, project, 'services_url', '//oslc:ServiceProvider/@rdf:about', func=get_first)
                self._add_from_xml(project_info, project, 'registry', './/jp:consumerRegistry/@rdf:resource', func=get_first)
                self._add_from_xml(project_info, project, 'details', './/oslc:details//@rdf:resource', func=get_first)
                catalog['projects'][project_info['title']] = project_info

                # -- List of services related to a particular project
                pa_services = self._get_xml(project_info['services_url'], project_info['title'] + " Project Services")
                # note: The problem here is that within a service section there are multiple (service) items...
                services = pa_services.xpath('.//oslc:Service/*', namespaces=self.namespace)
                for service in services:
                    # Note: The info below seems a little stressed-- It's kind of random...
                    service_info = {}
                    self._add_from_xml(service_info, service, 'title', './/dcterms:title', func=get_text)
                    self._add_from_xml(service_info, service, 'provider', '/oslc:ServiceProvider/@rdf:about', func=get_first)
                    self._add_from_xml(service_info, service, 'registry', 'jp:consumerRegistry/@rdf:resource', func=get_first)
                    self._add_from_xml(service_info, service, 'details', 'oslc:details//@rdf:resource', func=get_first)
                    if not service_info['title']:
                        # Actually, everything is empty... Maybe you should print it and see what it is...
                        # Note: this seems to catch a domain entry at the same level as the names service, groupped
                        # Note: under a service tag... Implies that there's something I don't understand. :-)
                        self.logger.warning("Could not find name of service: %s", etree.tostring(service, pretty_print=True))
                        continue
                    if len(service_info)<3:
                        # Most servcies have 3 or more entries...
                        self.logger.warning("Only partially decoded service: %s", etree.tostring(service, pretty_print=True))

                    project_info['services'][service_info['title']] = service_info


j = Jazz(server_alias="dng", config_path=JAZZ_CONFIG_PATH, namespace=olsc_namespaces)

pass