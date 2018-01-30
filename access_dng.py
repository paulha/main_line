# -- Support
import sys
from os.path import pathsep, dirname, realpath

import lxml as etree
import pandas as pd
import requests
from urllib.parse import urlencode
import urllib3
import utility_funcs.logger_yaml as log
from lxml import etree
from utility_funcs.search import get_server_info

urllib3.disable_warnings()

# -- Set up logger...
LOG_CONFIG_FILE = 'logging.yaml'+pathsep+dirname(realpath(sys.argv[0]))+'/logging.yaml'
log.setup_logging("logging.yaml", override={'handlers': {'info_file_handler': {'filename': 'access_dng.log'}}})
log.logger.setLevel(log.logging.getLevelName("INFO"))
log.logger.disabled = False

JAZZ_CONFIG_PATH = f"{dirname(realpath(sys.argv[0]))}/config.yaml{pathsep}~/.jazz/config.yaml"

class Jazz(requests.Session):

    def _get_text(x):
        return x[0].text if len(x) > 0 else ""

    def _get_first(x):
        return x[0] if len(x) > 0 else None

    def _get_xml(self, url, op_name="", mode="a"):
        response = self.get(url,
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

        logger(f"{op_name} response: {response.status_code}")
        logger(f"{op_name} cookies: {response.cookies}")
        logger(f"{op_name} headers: {response.headers}")
        logger(f"{url}\n{response.text}\n====")

        if op_name:
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

    def __init__(self, server_alias=None, config_path=None, namespace=None, log=log):
        requests.Session.__init__(self)
        self.RootServices = {}
        self.logger = log.logger
        self.namespace = namespace
        self.reset_list = []

        try:
            self.jazz_config = get_server_info(server_alias, config_path)  # possible FileNotFoundError
        except FileNotFoundError as f:
            self.log.fatal("Can't open JAZZ authentication configuration file: %s" % f)
            raise FileNotFoundError("Can't find Jazz configuration file", JAZZ_CONFIG_PATH)

        self.logger.info(f"Using JAMA server instance {self.jazz_config['host']}{self.jazz_config['instance']}")

        login_response = self.post(f"{self.jazz_config['host']}{self.jazz_config['instance']}/auth/j_security_check",
                                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                                   data=f"j_username={self.jazz_config['username']}&j_password={self.jazz_config['password']}",
                                   verify=False)
        self.logger.debug(f"Login response: {login_response.status_code}")
        self.logger.debug(f"Login cookies: {login_response.cookies}")
        # print(f"{login_response.text}\n=========================")

        pa_root_services = self._get_xml(f"{self.jazz_config['host']}{self.jazz_config['instance']}/rootservices", "Root Services")
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

    def get_service_provider(self):

        project_xml_tree = self._get_xml(self.RootServices['catalogs'][0]['url'], "Project Catalog")
        service_provider = project_xml_tree.xpath("//oslc:ServiceProvider[dcterms:title='" \
                                                  + self.jazz_config.['project'] + "']/./@rdf:about",
                                                  namespaces=self.namespace)
        return service_provider[0]

    def query(self, oslc_prefix=None, oslc_select=None, oslc_where=None):
        query_section = self.RootServices['catalogs'][0]['projects'][self.jazz_config['project']]['services']['Query Capability']
        query = query_section['queryBase']
        # -- Note: Something about 'calm' upsets things...
        prefix = oslc_prefix if oslc_prefix is not None \
                    else ",".join([f'{key}=<{link}>' for key, link in self.namespace.items()])

        # prefix = f"&oslc.prefix={prefix}" #   if oslc_prefix is not None else ""
        prefix = "&"+urlencode({'oslc.prefix': prefix})
        # select = f"&oslc.select={oslc_select}" if oslc_select is not None else ""
        select = "&"+urlencode({'oslc.select': oslc_select}) if oslc_select is not None else ""
        # where = f"&oslc.where={oslc_where}" if oslc_where is not None else ""
        where = "&"+urlencode({'oslc.where': oslc_where}) if oslc_where is not None else ""
        query_text = f"{query}{prefix}{select}{where}"
        query_root = self._get_xml(query_text, "Query")
        query_result = {'query_text': query_text, 'query_root': query_root, 'query_result': etree.tostring(query_root)}
        self._add_from_xml(query_result, query_root, 'result', './oslc:ResponseInfo/dcterms:title', func=Jazz._get_text)
        self._add_from_xml(query_result, query_root, 'about', './rdf:Description/@rdf:about', func=Jazz._get_first)
        self._add_from_xml(query_result, query_root, 'RequirementCollections', '//oslc_rm:RequirementCollection/@rdf:about')
        self._add_from_xml(query_result, query_root, 'Requirements', '//oslc_rm:Requirement/@rdf:about')
        return query_result

    def _get_resources(self, resource_list, section_tag='resources'):
        return [self._get_xml(resource_url, section_tag, mode="a+") for resource_url in resource_list]


    def read(self, resource_url, section_tag='item'):
        root_element = self._get_xml(resource_url, section_tag, mode="a+")
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

    def discover_root_folder():
        query = new HttpGet(self.get_service_provider());
        query.addHeader("Accept", "application/rdf+xml");
        query.addHeader("OSLC-Core-Version", "2.0");

        # -- Access to the Service Providers catalog
        response = HttpUtils.sendGetForSecureDocument( server, query, login, password, httpclient, JTS_Server);

        if (response.getStatusLine().getStatusCode() != 200):
            response.getEntity().consumeContent();
            throw new HttpResponseException(response.getStatusLine().getStatusCode(), response.getStatusLine().getReasonPhrase());

        // Define the XPath evaluation environment
        xpath = getXpathNamespace();

        queryCapability = "//oslc:QueryCapability[dcterms:title=\"Folder Query Capability\"]/oslc:queryBase/@rdf:resource";

        # -- Parse the response body to retrieve the catalog URI
        InputSource source = new InputSource(response.getEntity().getContent());
        Node attribute = (Node) (xpath.evaluate(queryCapability, source, XPathConstants.NODE));
        String queryCapabilityUrl = attribute.getTextContent();
        response.getEntity().consumeContent();

        query = new HttpGet(queryCapabilityUrl);
        query.addHeader("Accept", "application/rdf+xml");
        query.addHeader("OSLC-Core-Version", "2.0");

        # --Access to the Service Providers catalog
        response = HttpUtils.sendGetForSecureDocument(
        server, query, login, password, httpclient, JTS_Server);

        if (response.getStatusLine().getStatusCode() != 200):
            response.getEntity().consumeContent();
            throw new HttpResponseException(response.getStatusLine().getStatusCode(), response.getStatusLine().getReasonPhrase());

        queryCapability = "//nav:folder[dcterms:title=\"root\"]/@rdf:about";

        # --Parse the response body to retrieve the catalog URI
        xpath = getXpathNamespace();
        source = new InputSource(response.getEntity().getContent());
        attribute = (Node) (xpath.evaluate(queryCapability, source, XPathConstants.NODE));
        String rootFolder = attribute.getTextContent();
        response.getEntity().consumeContent();

        return rootFolder;


    def createFolder(self, folderName: str, parentfolder: str=None, project: str=None) -> str:
        serviceProviderUrl = self.get_service_provider()

        # Get the Project ID String
        projectID = serviceProviderUrl.substring(0, serviceProviderUrl.lastIndexOf("/"));
        projectID = projectID.substring(projectID.lastIndexOf("/") + 1);

        if (folderName == null):
            folderName = "OSLC Created";

        if (parentfolder == null):
            # -- lets create it on the root \
            # -- parentfolder = this.server + "/folders/" + projectID;
            # -- https: // jazz.net / jazz03 / web / projects / Requirements % 20 Management # action=com.ibm.team.workitem.viewWorkItem&id=114458
            parentfolder = discoverRootFolder(serviceProviderUrl);

        # -- 6.0 update - changed to using rm server for targetProject URL, not the JTS server
        # -- Create the URL Creation factory
        String targetProject = "?projectURL=" + this.server + "/process/project-areas/" + projectID;
        String folderCreationFactory = this.server + "/folders" + targetProject;

        xml = f"""
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
                    <dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">{folderName}</dcterms:title>
                    <nav:parent rdf:resource="{parentfolder}"/>
                </rdf:Description>
            </rdf:RDF>
        """;

        // Post to the Requirement Factory
        
        HttpPost post = new HttpPost(folderCreationFactory);
        post.addHeader("Accept", "application/rdf+xml");
        post.addHeader("Content-Type", "application/rdf+xml");
        post.addHeader("OSLC-Core-Version", "2.0");
        post.setEntity(new StringEntity(xml, HTTP.UTF_8));
        // -- FIXME: Throws a 302 error 
        HttpResponse sendPostForSecureDocument = HttpUtils.sendPostForSecureDocument(server, post, login, password, httpclient);
        
        Header folderLocation = sendPostForSecureDocument.getFirstHeader("Location");
        sendPostForSecureDocument.getEntity().consumeContent();
        return folderLocation.getValue();


def main():
    j = Jazz(server_alias="sandbox", config_path=JAZZ_CONFIG_PATH)
    query_result = j.query(# oslc_prefix='rdf=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>,calm=<http://jazz.net/xmlns/prod/jazz/calm/1.0>,rm=<http://www.ibm.com/xmlns/rdm/rdf/>,oslc=<http://open-services.net/ns/core#>,jp10=<http://jazz.net/xmlns/prod/jazz/process/1.0/>,oslc_config=<http://open-services.net/ns/config#>,dcterms=<http://purl.org/dc/terms/>',
                           oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
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
