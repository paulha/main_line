
# import lxml as etree
from lxml import etree
import re
import utility_funcs.logger_yaml as log
from jazz.dng import Jazz

class DNGRequest:
    # -- Note: ETag is stored in attrib list of xml_root
    def __init__(self, jazz_client: Jazz,
                 artifact_uri: str=None, title: str = None, description: str=None, parent: str=None, xml_root=None,
                 instance_shape: str=None, property_uri: str=None,
                 primary_list: list=[], primary: dict={},
                 literal_property_list: list=[], literal_properties: dict={},
                 resource_property_list: list=[], resource_properties: dict={},
                 op_name=None ):
        self.artifact_uri = artifact_uri
        self.description = description
        self.instanceShape = instance_shape
        self.jazz_client = jazz_client
        self.op_name = op_name
        self.parent = parent
        self.title = title
        self.xml_root = xml_root

        self.primary_list = primary_list
        self.primary = primary
        self.literal_property_list = literal_property_list
        self.literal_properties = literal_properties
        self.resource_property_list = resource_property_list
        self.resource_properties = resource_properties

        self.property_uri = property_uri                        # (Not sure how this one might be used,,,)

        self.E_tag = None

    def __getitem__(self, key):
        if hasattr(self, key):
            return getattr(self, key)

        if key in self.primary_list:
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

        if key in self.primary_list:
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

    def get(self) -> object:
        """Make a request to the server to please read get this thing..."""
        if self.artifact_uri is None:
            raise Exception("artifact_uri is not set")

        self.xml_root = self.jazz_client._get_xml(self.artifact_uri, op_name=self.op_name)
        return self

    def put(self) -> object:
        # TODO: previews of coming attractions!
        text = etree.tostring(self.xml_root, pretty_print=True)
        etag = self.xml_root.attrib['ETag'] if 'ETag' in self.xml_root.attrib else None
        del self.xml_root.attrib['ETag']
        log.logger.info(f"About to put {text}")
        response = self.jazz_client._post_xml(self.artifact_uri,
                                              data=text,
                                              if_match=etag)
        log.logger.info(f"Result was {response}")
        return self


class RequirementCollection(DNGRequest):
    """
    <!-- This example is missing the 'uses' tag, which includes a resource... -->
    <oslc_rm:RequirementCollection rdf:about="https://rtc-sbox.intel.com/rrc/resources/_qjQ-AwhLEeit3bw9wrTg3Q">
        <rt:_ySe9YXNnEeecjP8b5e9Miw rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-02T19:02:50.624Z</rt:_ySe9YXNnEeecjP8b5e9Miw>
        <dcterms:description>Looks like this can contain other artifacts. :-)</dcterms:description>
        <oslc:instanceShape rdf:resource="https://rtc-sbox.intel.com/rrc/types/_GeAbgnNoEeecjP8b5e9Miw"/>
        <dcterms:title>Copy of This is a &quot;Collection Release&quot;</dcterms:title>
        <rt:_yQ2lunNnEeecjP8b5e9Miw rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        <dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-02T19:02:50.624Z</dcterms:modified>
        <dcterms:creator rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        <dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-02T19:02:50.624Z</dcterms:created>
        <rt:_yX1-h3NnEeecjP8b5e9Miw rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-02T19:02:50.624Z</rt:_yX1-h3NnEeecjP8b5e9Miw>
        <f1:accessControl rdf:resource="https://rtc-sbox.intel.com/rrc/accessControl/_xf5p4XNnEeecjP8b5e9Miw"/>
        <nav:parent rdf:resource="https://rtc-sbox.intel.com/rrc/folders/_4p0zw_J4Eeec-bwG5--tlA"/>
        <dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">244084</dcterms:identifier>
        <rmTypes:ArtifactFormat rdf:resource="https://rtc-sbox.intel.com/rrc/types/_yBhwT3NnEeecjP8b5e9Miw#Collection"/>
        <dcterms:contributor rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        <rt:_yUH8KXNnEeecjP8b5e9Miw rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
    </oslc_rm:RequirementCollection>

    """
    def __init__(self, jazz_client: Jazz, artifact_uri: str=None, instance_shape: str=None,
                 title: str = None, description: str = None, parent: str = None, xml_root=None,
                 property_uri: str=None, op_name: str=None, **kwargs):
        super().__init__(jazz_client, artifact_uri=artifact_uri, title=title, description=description, parent=parent, xml_root=xml_root,
                         primary_list=['uri', 'title', 'identifier', 'type', 'description', 'subject', 'creator', 'modified'],
                         property_uri=property_uri, instance_shape=instance_shape,
                         resource_property_list=['primaryText'], op_name=op_name)

        for key in kwargs:
            self[key] = kwargs[key]


class RequirementRequest(DNGRequest):
    """
    <oslc_rm:Requirement rdf:about="https://rtc-sbox.intel.com/rrc/resources/_d6-AwwhLEeit3bw9wrTg3Q">
        <rt:_ySe9YXNnEeecjP8b5e9Miw rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-02T19:01:25.882Z</rt:_ySe9YXNnEeecjP8b5e9Miw>
        <dcterms:description></dcterms:description>
        <oslc:instanceShape rdf:resource="https://rtc-sbox.intel.com/rrc/types/_DyURUXNoEeecjP8b5e9Miw"/>
        <jazz_rm:primaryText>PFH -- An Initial Requirement to play with</jazz_rm:primaryText>
        <dcterms:title>Copy of PFH -- An Initial Requirement to play with</dcterms:title>
        <rt:_yQ2lunNnEeecjP8b5e9Miw rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        <dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-02T19:01:25.882Z</dcterms:modified>
        <dcterms:creator rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        <dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-02T19:01:25.882Z</dcterms:created>
        <rt:_yX1-h3NnEeecjP8b5e9Miw rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-02T19:01:25.882Z</rt:_yX1-h3NnEeecjP8b5e9Miw>
        <f1:accessControl rdf:resource="https://rtc-sbox.intel.com/rrc/accessControl/_xf5p4XNnEeecjP8b5e9Miw"/>
        <nav:parent rdf:resource="https://rtc-sbox.intel.com/rrc/folders/_4p0zw_J4Eeec-bwG5--tlA"/>
        <dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">244083</dcterms:identifier>
        <rmTypes:ArtifactFormat rdf:resource="https://rtc-sbox.intel.com/rrc/types/_yBhwT3NnEeecjP8b5e9Miw#Text"/>
        <dcterms:contributor rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        <rt:_yUH8KXNnEeecjP8b5e9Miw rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
    </oslc_rm:Requirement>

    """
    def __init__(self, jazz_client: Jazz, artifact_uri: str=None, instance_shape: str=None,
                 title: str = None, description: str = None, parent: str = None, xml_root=None,
                 property_uri: str=None, op_name: str=None, **kwargs):
        super().__init__(jazz_client, artifact_uri=artifact_uri, title=title, description=description, parent=parent, xml_root=xml_root,
                         primary_list=['uri', 'title', 'identifier', 'type', 'description', 'subject', 'creator', 'modified'],
                         property_uri=property_uri, instance_shape=instance_shape,
                         resource_property_list=['primaryText'], op_name=op_name)

        for key in kwargs:
            self[key] = kwargs[key]

    def initialize_from_xml(self, element) -> DNGRequest:
        for item in element.xpath("//oslc_rm:Requirement/*", namespaces=Jazz.xpath_namespace()):
            tag = item.tag
            tag = re.sub(r"^{.*}", "", tag)
            # todo: Need special handling for oslc:instanceShape, nav:parent, and rm_jazz:primaryText rdf:parseType="Literal"
            if tag == 'instanceShape':
                e = item.xpath("//oslc:instanceShape/@rdf:resource", namespaces=Jazz.xpath_namespace())
                if len(e) == 1:
                    self[tag] = e[0]
                else:
                    log.logger.error(f"Could not resolve instanceShape: {etree.tostring(item)}")

            elif tag == 'parent':
                e = item.xpath("//nav:parent/@rdf:resource", namespaces=Jazz.xpath_namespace())
                if len(e) == 1:
                    self[tag] = e[0]
                else:
                    log.logger.error(f"Could not resolve parent: {etree.tostring(item)}")

            elif tag == 'primaryText':
                e = item.xpath("//rm_jazz:primaryText/*", namespaces=Jazz.xpath_namespace())
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
    def __init__(self, jazz_client: Jazz, folder_uri: str=None,
                 title: str = None, description: str=None, parent: str=None, xml_root=None, op_name: str=None):
        super().__init__(jazz_client, title=title, description=description, parent=parent, xml_root=xml_root, op_name=op_name)
        self.folder_uri = folder_uri
        self.op_name = op_name
        self.subfolders = None
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
        self.title = self.xml_root.xpath("//dcterms:title/text()", namespaces=Jazz.xpath_namespace())[0]
        self.description = self.xml_root.xpath("//dcterms:description/text()", namespaces=Jazz.xpath_namespace())[0]
        self.parent = self.xml_root.xpath("//nav:parent/@rdf:resource", namespaces=Jazz.xpath_namespace())[0]
        self.component = self.xml_root.xpath("//oslc_config:component/@rdf:resource", namespaces=Jazz.xpath_namespace())[0]
        self.subfolders = self.xml_root.xpath("//nav:subfolders/@rdf:resource", namespaces=Jazz.xpath_namespace())[0]
        self.service_provider = self.xml_root.xpath("//oslc:serviceProvider/@rdf:resource", namespaces=Jazz.xpath_namespace())[0]

        self.subfolders_xml_root = self.jazz_client._get_xml(self.subfolders, op_name=self.op_name)
        return self

    def get_root_folder_uri(self, op_name: str=None) -> str:
        folder_query_xpath = '//oslc:QueryCapability[dcterms:title="Folder Query Capability"]/oslc:queryBase/@rdf:resource'
        folder_query_uri = self.jazz_client.get_service_provider_root().xpath(folder_query_xpath,
                                                                              namespaces=Jazz.xpath_namespace())[0]
        folder_result_xml = self.jazz_client._get_xml(folder_query_uri, op_name=op_name)
        root_path_uri = folder_result_xml.xpath("//nav:folder[dcterms:title=\"root\"]/@rdf:about",
                                                namespaces=Jazz.xpath_namespace())[0]
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
                subfolder_root_list = subfolders_root.xpath("//nav:folder", namespaces=Jazz.xpath_namespace())
                for candidate in subfolder_root_list:
                    name = candidate.xpath(".//dcterms:title/text()", namespaces=Jazz.xpath_namespace())[0]
                    if dir_name == name:
                        new_group_uri = candidate.xpath(".//nav:subfolders/@rdf:resource", namespaces=Jazz.xpath_namespace())[0]
                        about = candidate.xpath("../nav:folder/@rdf:about", namespaces=Jazz.xpath_namespace())[0]
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

    def get_folder_artifacts(self, path: str=None) -> list:
        path = path if path is not None else ""
        parent_folder_uri = self.get_matching_folder_uri(path)
        parent_list = " ".join([f"<{uri}>" for uri in parent_folder_uri])
        artifacts = self.jazz_client.query(oslc_where=f"nav:parent in [{parent_list}]",
                                           oslc_select="*")
        # Yes! It works! :-)
        return artifacts

