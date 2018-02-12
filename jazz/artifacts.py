
from lxml import etree
import re
import utility_funcs.logger_yaml as log
from .dng import Jazz


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

        self.primary_list = primary_list
        self.primary = primary
        self.literal_property_list = literal_property_list
        self.literal_properties = literal_properties
        self.resource_property_list = resource_property_list
        self.resource_properties = resource_properties

        self.property_uri = property_uri                        # (Not sure how this one might be used,,,)

        self.E_tag = None

        self.xml_root = xml_root
        if self.xml_root is not None:
            self.init_from_xml_root()

    def xpath_get_item(self, xpath, func=lambda x: x[0] if len(x) > 0 else None):
        element = self.xml_root.xpath(xpath, namespaces=Jazz.xpath_namespace())
        return func(element)

    def init_from_xml_root(self):
        # -- Is there a way to get this without programming every field?
        # todo: need to pick up the folder_uri, also...
        # -- Should always have a resource URL...
        self.artifact_uri = self.xpath_get_item("//*/@rdf:about")
        self.title = self.xpath_get_item("//dcterms:title/text()")
        self.description = self.xpath_get_item("//dcterms:description/text()")
        self.parent = self.xpath_get_item("//nav:parent/@rdf:resource")

        # Is this appropriate in all cases?
        self.initialize_from_xml(self.xml_root)

    def initialize_from_xml(self, element) -> object:
        """This tries to read other values out of the xml object..."""
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
        def check_response(response):
            # log.logger.info(f"Result was {response}")
            if response.status_code >= 400 and response.status_code <= 499:
                raise Exception(f"Result was {response}. Couldn't put artifact.")
            pass

        text = etree.tostring(self.xml_root, pretty_print=True)
        etag = self.xml_root.attrib['ETag'] if 'ETag' in self.xml_root.attrib else None
        del self.xml_root.attrib['ETag']
        log.logger.info(f"About to put {text}")
        self.xml_root = self.jazz_client._put_xml(self.artifact_uri,
                                                  data=text,
                                                  if_match=etag,
                                                  op_name=self.op_name,
                                                  check=check_response)

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
    def __init__(self, jazz_client: object, artifact_uri: str=None, instance_shape: str=None,
                 title: str = None, description: str = None, parent: str = None, xml_root=None,
                 property_uri: str=None, op_name: str=None, **kwargs):
        super().__init__(jazz_client, artifact_uri=artifact_uri, title=title, description=description, parent=parent, xml_root=xml_root,
                         primary_list=['uri', 'title', 'identifier', 'type', 'description', 'subject', 'creator', 'modified'],
                         property_uri=property_uri, instance_shape=instance_shape,
                         resource_property_list=['primaryText'], op_name=op_name)

        for key in kwargs:
            self[key] = kwargs[key]


class Requirement(DNGRequest):
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
    def __init__(self, jazz_client: object, artifact_uri: str=None, instance_shape: str=None,
                 title: str = None, description: str = None, parent: str = None, xml_root=None,
                 property_uri: str=None, op_name: str=None, **kwargs):
        super().__init__(jazz_client, artifact_uri=artifact_uri, title=title, description=description,
                         parent=parent, xml_root=xml_root,
                         primary_list=['uri', 'title', 'identifier', 'type', 'description', 'subject', 'creator', 'modified'],
                         property_uri=property_uri, instance_shape=instance_shape,
                         resource_property_list=['primaryText'], op_name=op_name)

        for key in kwargs:
            self[key] = kwargs[key]

    @classmethod
    def create_requirement(cls, client: Jazz, name: str=None, description: str=None, parent_folder: object=None,
                           resource_type: str="http://open-services.net/ns/rm#Requirement",
                           op_name: str=None) -> object:
        client.logger.info(f"create_requirement('{parent_folder.artifact_uri}')")
        shape_uri = client.get_shape_url(shape_type=client.jazz_config['requirement_shape'])
        xml = f"""
            <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/terms/"
                     xmlns:public_rm_10="http://www.ibm.com/xmlns/rm/public/1.0/"
                     xmlns:calm="http://jazz.net/xmlns/prod/jazz/calm/1.0/" xmlns:rm="http://www.ibm.com/xmlns/rdm/rdf/"
                     xmlns:acp="http://jazz.net/ns/acp#" xmlns:rm_property="https://grarrc.ibm.com:9443/rm/types/"
                     xmlns:oslc="http://open-services.net/ns/core#" xmlns:nav="http://jazz.net/ns/rm/navigation#"
                     xmlns:oslc_rm="http://open-services.net/ns/rm#">
                <rdf:Description rdf:about="">
                    <rdf:type rdf:resource="http://open-services.net/ns/rm#Requirement"/>
                    <dc:description rdf:parseType="Literal">{description if description is not None else ''}</dc:description>
                    <dc:title rdf:parseType="Literal">{name}</dc:title>
                    <oslc:instanceShape rdf:resource="{shape_uri}"/>
                    <nav:parent rdf:resource="{parent_folder.artifact_uri if parent_folder is not None else ''}"/>
                </rdf:Description>
            </rdf:RDF>
            """
        requirement_creation_factory = client.get_requirement_factory()

        # _post_xml actually receives the returned content for the requested resource.
        response = None

        def get_response(resp):
            nonlocal response
            response = resp

        xml_response = client._post_xml(requirement_creation_factory, op_name=op_name, data=xml, check=get_response)

        if response.status_code not in [201]:
            raise PermissionError(f"Unable to create Requirement '{name}', result status {response.status_code}")

        return Requirement(client, xml_root=xml_response)


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
    """
    On subfolders:
    
    -   Initially, a folder is created with no subfolder list, implying that it gets created somehow...
    
    -   Subfolders are added to and removed from the current subfolder list to create and delete subfolders.
    
    -   Creating a folder that names /this/ folder as a parent would be what creates the subfolder list, no?
        So no separate add operation is required. I suppose updating a folder after changing/nulling the 
        folder's parent link would have the effect of deleting the item as a subfolder. If an item has no
        "valid" parent, what is its status? 
        
        Need to investigate...
    
    -   Does this same logic apply to Requirements?
    
    """
    root_folder = None

    def __init__(self, jazz_client: object, folder_uri: str=None,
                 title: str = None, description: str=None, parent: str=None, xml_root=None, op_name: str=None):
        super().__init__(jazz_client, title=title, description=description, parent=parent, xml_root=xml_root, op_name=op_name)
        self.artifact_uri = folder_uri
        self.op_name = op_name
        self.subfolders = None
        self.component = None
        self.subfolders = None
        self.subfolders_xml_root = None
        self.service_provider = None

        # FIXME: if xml_root has been specified, then need to init from that record...
        if self.xml_root is not None:
            self.init_from_xml_root()
        elif self.artifact_uri is not None:
            self.read(self.artifact_uri)
        else:
            self.read(self.get_root_folder_uri(op_name=op_name))

    def init_from_xml_root(self):
        super().init_from_xml_root()
        self.component = self.xpath_get_item("//oslc_config:component/@rdf:resource")
        self.service_provider = self.xpath_get_item("//oslc:serviceProvider/@rdf:resource")
        self.subfolders = self.xpath_get_item("//nav:subfolders/@rdf:resource")
        if self.subfolders is not None:
            self.subfolders_xml_root = self .jazz_client._get_xml(self.subfolders, op_name=self.op_name)

    def read(self, folder_uri: str) -> DNGRequest:
        self.artifact_uri = folder_uri
        self.xml_root = self.jazz_client._get_xml(self.artifact_uri, op_name=self.op_name)
        self.init_from_xml_root()
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

    def get_folder_name(self, op_name=None) -> str:
        node = self.xml_root.xpath("//dcterms:title/text()", namespaces=Jazz.xpath_namespace())
        return node[0]

    def get_folder_artifacts(self, path: str=None) -> list:
        path = path if path is not None else ""
        parent_folder_uri = self.get_matching_folder_uri(path)
        parent_list = " ".join([f"<{uri}>" for uri in parent_folder_uri])
        artifacts = self.jazz_client.query(oslc_where=f"nav:parent in [{parent_list}]",
                                           oslc_select="*")
        # Yes! It works! :-)
        return artifacts

    def delete_folder(self):
        raise Exception("delete_folder() Not Yet Implemented")

    @classmethod
    def get_root_folder(cls, client: Jazz, op_name=None):
        if client.root_folder is None:
            folder_query_xpath = '//oslc:QueryCapability[dcterms:title="Folder Query Capability"]/oslc:queryBase/@rdf:resource'
            folder_query_uri = client.get_service_provider_root().xpath(folder_query_xpath, namespaces=Jazz.xpath_namespace())[0]

            folder_result_xml = client._get_xml(folder_query_uri, op_name=op_name)

            root_folder_xpath = "//nav:folder[dcterms:title=\"root\"]/@rdf:about"
            root_path_uri = folder_result_xml.xpath(root_folder_xpath, namespaces=Jazz.xpath_namespace())[0]
            client.root_folder = Folder(client, folder_uri=root_path_uri)

        # TODO: Return folder instead of URI
        return client.root_folder

    @classmethod
    def create_folder(cls, client: Jazz, name: str=None, parent_folder: str=None, op_name: str=None) -> object:
        client.logger.info(f"create_folder('{name}')")

        service_provider_url = client.get_service_provider()

        # Get the Project ID String
        project_id= re.split('/', service_provider_url)[-2]

        if name is None:
            name = "OSLC Created";

        if parent_folder is None:
            parent_folder = Folder.get_root_folder(client)

        target_project = "?projectURL=" + client.jazz_config['host'] + client.jazz_config['instance'] + "/process/project-areas/" + project_id
        folder_creation_factory = client.jazz_config['host'] + client.jazz_config['instance'] + "/folders" + target_project;

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
                    <dcterms:title rdf:datatype="http://www.w3.org/2001/XMLSchema#string">{name}</dcterms:title>
                    <nav:parent rdf:resource="{parent_folder.artifact_uri}"/>
                </rdf:Description>
            </rdf:RDF>
        '''
        response = None

        def get_response(resp):
            nonlocal response
            response = resp

        xml_response = client._post_xml(folder_creation_factory, op_name=op_name, data=xml, check=get_response)

        if response.status_code not in [201]:
            raise PermissionError(f"Unable to create folder '{folder_name}', result status {response.status_code}")

        return Folder(client, xml_root=xml_response)
