
import lxml as etree
import re
import utility_funcs.logger_yaml as log
from jazz.dng import Jazz

class DNGRequest:
    def xpath_namespaces(self):
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

class RequirementRequest(DNGRequest):
    def __init__(self, property_uri: str, instanceShape: str, parent: str, **kwargs ):
        self.property_uri = property_uri
        self.instanceShape = instanceShape
        self.parent = parent
        self.primary = {}
        self.literal_property_list = []
        self.literal_properties = {}
        self.resource_property_list = ['primaryText']
        self.resource_properties = {}

        for key in kwargs:
            self[key] = kwargs[key]

    def __getitem__(self, key):
        if hasattr(self, key):
            return getattr(self, key)

        if key in ['uri', 'title', 'identifier', 'type', 'description', 'subject', 'creator', 'modified']:
            return self.primary[key]

        # -- Handle literal properties
        if key in self.literal_property_list:
            return self.literal_property[key]

        # -- Handle resource properties
        if key in self.resource_property_list:
            return self.resource_property[key]

        raise LookupError(f"Unknown field name: {key}")


    def __setitem__(self, key, value):
        if hasattr(self, key):
            setattr(self, key, value)
            return self

        if key in ['uri', 'title', 'identifier', 'type', 'description', 'subject', 'creator', 'modified']:
            self.primary[key] = value
            return self

        # -- Handle literal properties
        if key in self.literal_property_list:
            self.literal_properties[key] = value
            return self

        # -- Handle resource properties
        if key in self.resource_property_list:
            self.resource_properties[key] = value
            return self

        raise LookupError(f"Unknown field name: {key}")

    def initialize_from_xml(self, element) -> DNGRequest:
        for item in element.xpath("//oslc_rm:Requirement/*", namespaces=self.xpath_namespaces()):
            tag = item.tag
            tag = re.sub(r"^{.*}", "", tag)
            # todo: Need special handling for oslc:instanceShape, nav:parent, and rm_jazz:primaryText rdf:parseType="Literal"
            if tag == 'instanceShape':
                e = item.xpath("//oslc:instanceShape/@rdf:resource", namespaces=self.xpath_namespaces())
                if len(e) == 1:
                    self[tag] = e[0]
                else:
                    log.logger.error(f"Could not resolve instanceShape: {etree.tostring(item)}")

            elif tag == 'parent':
                e = item.xpath("//nav:parent/@rdf:resource", namespaces=self.xpath_namespaces())
                if len(e) == 1:
                    self[tag] = e[0]
                else:
                    log.logger.error(f"Could not resolve parent: {etree.tostring(item)}")

            elif tag == 'primaryText':
                e = item.xpath("//rm_jazz:primaryText/*", namespaces=self.xpath_namespaces())
                if len(e) == 1:
                    self[tag] = e[0]
                else:
                    log.logger.error(f"Could not resolve primaryText: {etree.tostring(item)}")

            else:
                self[tag] = item.text
        return self

class Folder(DNGRequest):
    """
    <nav:folder rdf:about="https://jazz.net/sandbox01-rm/folders/_IAr-IfJ7EeejvrGNyS30YA">
        <dcterms:title>root</dcterms:title>
        <dcterms:description>root</dcterms:description>
        <nav:parent rdf:resource="https://jazz.net/sandbox01-rm/process/project-areas/_H6U3cPJ7EeejvrGNyS30YA"/>
        <oslc_config:component rdf:resource="https://jazz.net/sandbox01-rm/cm/component/_H_NXcPJ7EeejvrGNyS30YA"/>
        <nav:subfolders rdf:resource="https://jazz.net/sandbox01-rm/folders?oslc.where=public_rm:parent=https://jazz.net/sandbox01-rm/folders/_IAr-IfJ7EeejvrGNyS30YA"/>
        <oslc:serviceProvider rdf:resource="https://jazz.net/sandbox01-rm/oslc_rm/_H6U3cPJ7EeejvrGNyS30YA/services.xml" />
    </nav:folder>

    """
    def __init__(self, jazz_client: Jazz, folder_uri: str=None, op_name: str=None):
        self.jazz_client = jazz_client
        self.folder_uri = folder_uri
        self.op_name = op_name
        self.xml_root = None
        self.subfolders = None
        self.title = None
        self.description = None
        self.parent = None
        self.component = None
        self.subfolders = None
        self.service_provider = None

        if self.folder_uri is not None:
            self.read(self.folder_uri)
        else:
            self.read(self.get_root_folder_uri(op_name=op_name))

    def read(self, folder_uri: str) -> DNGRequest:
        self.folder_uri = folder_uri
        self.xml_root = self.jazz_client._get_xml(self.folder_uri, op_name=self.op_name)
        # -- Is there a way to get this without programming every field?
        self.title = self.xml_root.xpath("//dcterms:title/text()", namespaces=self.xpath_namespaces())[0]
        self.description = self.xml_root.xpath("//dcterms:description/text()", namespaces=self.xpath_namespaces())[0]
        self.parent = self.xml_root.xpath("//nav:parent/@rdf:resource", namespaces=self.xpath_namespaces())[0]
        self.component = self.xml_root.xpath("//oslc_config:component/@rdf:resource", namespaces=self.xpath_namespaces())[0]
        self.subfolders = self.xml_root.xpath("//nav:subfolders/@rdf:resource", namespaces=self.xpath_namespaces())[0]
        self.service_provider = self.xml_root.xpath("//oslc:serviceProvider/@rdf:resource", namespaces=self.xpath_namespaces())[0]

        self.subfolders_xml_root = self.jazz_client._get_xml(self.subfolders, op_name=self.op_name)
        return self

    def get_root_folder_uri(self, op_name: str=None) -> str:
        folder_query_xpath = '//oslc:QueryCapability[dcterms:title="Folder Query Capability"]/oslc:queryBase/@rdf:resource'
        folder_query_uri = self.jazz_client.get_service_provider_root().xpath(folder_query_xpath,
                                                                              namespaces=self.xpath_namespaces())[0]
        folder_result_xml = self.jazz_client._get_xml(folder_query_uri, op_name=op_name)
        root_path_uri = folder_result_xml.xpath("//nav:folder[dcterms:title=\"root\"]/@rdf:about",
                                                namespaces=self.xpath_namespaces())[0]
        return root_path_uri

    def get_matching_folder_uri(self, path: str) -> list:
        """
        On entry, the initial path to the subfolder service is in self.subfolders.

        Eventually, if the path begins with "/", it starts at the root of the system.

        :param path:    Desired path, separated by "/"
        :return:        Folder for path
        """
        navigation_path = path.split("/")
        if navigation_path[0] == '':
            navigation_path = []

        subfolders_to_check = []
        subfolders_to_check.append(self.subfolders)
        next_matches_to_check = []
        last_result = []

        for dir_name in navigation_path:
            # -- Read the subfolders of the current folder, scheduling the associated subfolders if there is a match.
            result = []
            for folder in subfolders_to_check:
                subfolders_root = self.jazz_client._get_xml(folder, op_name=self.op_name)
                subfolder_root_list = subfolders_root.xpath("//nav:folder", namespaces=self.xpath_namespaces())
                for candidate in subfolder_root_list:
                    name = candidate.xpath(".//dcterms:title/text()", namespaces=self.xpath_namespaces())[0]
                    if dir_name == name:
                        new_group_uri = candidate.xpath(".//nav:subfolders/@rdf:resource", namespaces=self.xpath_namespaces())[0]
                        about = candidate.xpath("../nav:folder/@rdf:about", namespaces=self.xpath_namespaces())[0]
                        result.append(about)
                        next_matches_to_check.append(new_group_uri)

            # -- All the folders have been considered and added if they match. Do a shift!
            if len(next_matches_to_check)==0:
                # -- We didn't find any matches this go around, we're done!
                return None

            last_result = result
            subfolders_to_check = next_matches_to_check
            next_matches_to_check = []

        # -- If we come out here, at least one match was found.
        return last_result