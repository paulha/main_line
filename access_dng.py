import urllib3
import requests
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

"""
Note: So here's a problem!

In the files coming from DNG, the oslc_rm name space has *two* different definitions, and that confuses the XML 
parser which apparently needs the local definition and that from the XML file to match before it believes that
the XML tags match.

Causes very flakey seeming problems. Grrr!

"""

olsc_namespaces_A = {
    'acp':'http://jazz.net/ns/acp#',
    'calm': 'http://jazz.net/xmlns/prod/jazz/calm/1.0/',
    'dc': 'http://purl.org/dc/terms/',
    'dcterms': 'http://purl.org/dc/terms/',
    'jazz_rm': 'http://jazz.net/ns/rm#',
    'jp': 'http://jazz.net/xmlns/prod/jazz/process/1.0/',
    'nav': 'http://jazz.net/ns/rm/navigation#',
    'oslc': 'http://open-services.net/ns/core#',
    # 'oslc_rm': 'http://open-services.net/ns/rm#',
    'oslc_rm': 'http://open-services.net/xmlns/rm/1.0/',  # -- FIXME: This is a serious problem...
    'oslc_config': 'http://open-services.net/ns/config#',
    'process': 'http://jazz.net/ns/process#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'rm_property': 'https://rtc.intel.com/dng0001001/types/',
}

olsc_namespaces_B = {
    'acp':'http://jazz.net/ns/acp#',
    'calm': 'http://jazz.net/xmlns/prod/jazz/calm/1.0/',
    'dc': 'http://purl.org/dc/terms/',
    'dcterms': 'http://purl.org/dc/terms/',
    'jazz_rm': 'http://jazz.net/ns/rm#',
    'jp': 'http://jazz.net/xmlns/prod/jazz/process/1.0/',
    'nav': 'http://jazz.net/ns/rm/navigation#',
    'oslc': 'http://open-services.net/ns/core#',
    'oslc_rm': 'http://open-services.net/ns/rm#',
    # 'oslc_rm': 'http://open-services.net/xmlns/rm/1.0/',  # -- FIXME: This is a serious problem...
    'oslc_config': 'http://open-services.net/ns/config#',
    'process': 'http://jazz.net/ns/process#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'rm_property': 'https://rtc.intel.com/dng0001001/types/',
}

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
        self.logger.info(f"{op_name} headers: {response.headers}")
        self.logger.debug(f"{url}\n{response.text}\n====")
        if op_name:
            with open(op_name + '.xml', mode) as f:
                f.write(response.text)

        response.raw.decode_content = True
        return etree.fromstring(response.text)

    def _add_from_xml(self, result: dict, element, tag: str=None, path: str=None, namespaces: dict=None, func=None):
        # todo: if the target already has an entry, convert to a list of entries. (Note, it might already be a list!)
        # note: that this is going to return a list of elements if there's more than one there...
        e = element.xpath(path, namespaces=namespaces if namespaces is not None else self.namespace)
        if e is not None and len(e) > 0:
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
        # fixme: This xpath does not work....
        self._add_from_xml(query_result, query_root, 'RequirementCollections',
                           '//oslc_rm:RequirementCollection/@rdf:about', func=None)
        # fixme: This xpath does not work....
        self._add_from_xml(query_result, query_root, 'Requirements',
                           '//oslc_rm:Requirement/@rdf:about', func=None)
        # note: This one does....
        self._add_from_xml(query_result, query_root, 'members',
                           '//rdfs:member/*/@rdf:about', func=None)
        return query_result

    def read(self, resource_url):
        root_element = self._get_xml(resource_url, "item", mode="a+")
        this_item = {}
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
        self._add_from_xml(this_item, root_element, 'rm_property:_5LMQKK_4EeekDP1y4xXYPQ', './rdf:Description/rm_property:_5LMQKK_4EeekDP1y4xXYPQ/@rdf:resource')
        self._add_from_xml(this_item, root_element, 'rm_property:_4G6Ioa_4EeekDP1y4xXYPQ', './rdf:Description/rm_property:_4G6Ioa_4EeekDP1y4xXYPQ/@rdf:resource')
        # -- Entry below should be for a collection...
        self._add_from_xml(this_item, root_element, 'uses', '//oslc_rm:uses/@rdf:resource')
        self.logger.debug(this_item)
        return this_item


def main():
    rdf = """<rdf:RDF
            xmlns:nav="http://jazz.net/ns/rm/navigation#"
            xmlns:acp="http://jazz.net/ns/acp#"
            xmlns:oslc_rm="http://open-services.net/ns/rm#"
            xmlns:oslc="http://open-services.net/ns/core#"
            xmlns:rm_property="https://rtc.intel.com/dng0001001/types/"
            xmlns:oslc_config="http://open-services.net/ns/config#"
            xmlns:oslc_auto="http://open-services.net/ns/auto#"
            xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:process="http://jazz.net/ns/process#"
            xmlns:jazz_rm="http://jazz.net/ns/rm#"
            xmlns:calm="http://jazz.net/xmlns/prod/jazz/calm/1.0/"
            xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
            xmlns:rm="http://www.ibm.com/xmlns/rdm/rdf/"
            xmlns:public_rm_10="http://www.ibm.com/xmlns/rm/public/1.0/"
            xmlns:dng_task="http://jazz.net/ns/rm/dng/task#"
            xmlns:dcterms="http://purl.org/dc/terms/"
            xmlns:acc="http://open-services.net/ns/core/acc#" > 
          <rdf:Description rdf:about="https://rtc.intel.com/dng0001001/resources/_92999fbcfdc04fd8b17022b35f53d76e">
            <oslc:serviceProvider rdf:resource="https://rtc.intel.com/dng0001001/oslc_rm/_zQHY0a_4EeekDP1y4xXYPQ/services.xml"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_485aa8ee04aa4161942f77a00d901872"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_8ff1b103e0f249ad92d410ec1104f636"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_da54d3edb8a7414298e1accdd29c17a6"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_1b90860b14c44bbebcf81930f08a5cbd"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_fb37bc708a0e4ce1bc12e69081404a79"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_7b28bfd10a1c44f4b003e81a878bcdc2"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_95a3fe44f9d04d84acc61f054aaf6f25"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_bd304f0e7cc54f0d8c4523e996f916f4"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_dff12d133bd242d5b7d056eacf9c97a2"/>
            <nav:parent rdf:resource="https://rtc.intel.com/dng0001001/folders/_2f0ccb1dc37c4c44aea875b823b98ec7"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_e8533fde7972481c9e72232a30ff15b7"/>
            <oslc:instanceShape rdf:resource="https://rtc.intel.com/dng0001001/types/_9upNMa_4EeekDP1y4xXYPQ"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_bba989544f2c40819a261826ce31231f"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_8a44037baafc467da441782b31aea27a"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_c008116ba7c34acc8501b8a26ce5734c"/>
            <rdf:type rdf:resource="http://open-services.net/ns/rm#RequirementCollection"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_effbc654bd2c4693b811ea83efc3f034"/>
            <dcterms:creator rdf:resource="https://rtc.intel.com/jts/users/balasu4x"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_4976a0a8e8a34d4596691cf9ae360b8e"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_9555dc098bd54a4c8c8055447ce9b9ab"/>
            <acp:accessControl rdf:resource="https://rtc.intel.com/dng0001001/accessControl/_zQHY0a_4EeekDP1y4xXYPQ"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_76fe4b0f58874d42a0d5917fbea11493"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_0c648e93a4584a05a17403be95b7f191"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_b3c6b624f2824f81aeedf32f97dbdec5"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_f65f137ff89e4821bcd6fee8093ca6e9"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_86a6ef634fd84e99809e1ff16ca78534"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_304dd9cf068f45029aef7ef0b9894ade"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_550693259a6c4ab28728433b5a79c477"/>
            <dcterms:contributor rdf:resource="https://rtc.intel.com/jts/users/rmbeatty"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_fa05960de017453e913d32ce6b7a4c6b"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_17815bff6e7447a9ac3251fabb1543cc"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_e1ea29aedc164af2b6f51b5fb08bb59f"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_a2c98a600df94dcabd542295e8de8fc5"/>
            <rdf:type rdf:resource="http://jazz.net/ns/rm#Module"/>
            <dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2017-11-21T18:32:23.221Z</dcterms:modified>
            <process:projectArea rdf:resource="https://rtc.intel.com/dng0001001/process/project-areas/_zQHY0a_4EeekDP1y4xXYPQ"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_e4b3246c17154bd9906e8473c9ca0081"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_e6eaca5f33b34efd91a43fdf79236b10"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_8d442c08a2234d2a9dc14c5972dbad35"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_b2a096c66d6c4adb9e2b63aa39906205"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_b1c8ce49a9e248f6984b8efe7a082351"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_8f42b3e239cb4ee39fe2e6fb65d93cce"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_4821bd552abe4a9f8cdc73fe1587a134"/>
            <dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#string">37694</dcterms:identifier>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_a89b601c755b4aacb87c4c5f246190ff"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_ae25f4b2ca4246e0bec192901ae4b46a"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_aada4f80336b47db9778017884b04d81"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_20945d2e18314c1b8540d648057c3e53"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_f75886bdea234a05acc5a33fe87ab306"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_99988900b2b84e42a7740ed42da018f8"/>
            <dcterms:title rdf:parseType="Literal">Template-PRD.doc</dcterms:title>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_9f1bfaead0cd4b0893116dc0e6237cf3"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_9ef4792340804b50bbc3862d051dfbad"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_169d61c7182b40ac80cd1914f270065d"/>
            <oslc_config:component rdf:resource="https://rtc.intel.com/dng0001001/cm/component/_zgCEIq_4EeekDP1y4xXYPQ"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_1001f0add679408f9f87367663a57a29"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_460fea184ae94e4c849a9b296ff1a9ed"/>
            <dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2017-10-13T09:29:34.698Z</dcterms:created>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_973ba3ec68a44e98a7d2c7bdfb044d1b"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_1826448a659b4f6bb3b83c0e1995d7dd"/>
            <oslc_rm:uses rdf:resource="https://rtc.intel.com/dng0001001/resources/_770f55eca68f4c079722867a4810fd35"/>
          </rdf:Description>
        </rdf:RDF>
        """
    root = etree.fromstring(rdf)
    e = root.xpath("//oslc_rm:uses/@rdf:resource", namespaces=olsc_namespaces_B)

    j = Jazz(server_alias="dng", config_path=JAZZ_CONFIG_PATH, namespace=olsc_namespaces_A)
    j.namespace = olsc_namespaces_B
    query_result = j.query_all()
    items = {item['identifier']: item for item in [j.read(member) for member in query_result['members'][:2]]}

    p = pd.DataFrame(items)

    # todo: Extend so you can make a query!

    log.logger.info(p)

    pass


if __name__ == '__main__':
    main()
