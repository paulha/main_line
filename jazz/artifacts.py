from collections import Iterable
from lxml import etree

import re
import utility_funcs.logger_yaml as log
from .dng import Jazz

class DNGRequest:
    pass

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

    def get_name(self, op_name=None) -> str:
        node = self.xml_root.xpath("//dcterms:title/text()", namespaces=Jazz.xpath_namespace())
        return node[0]

    def xpath_get_item(self, xpath, func=lambda x: x[0] if len(x) > 0 else None):
        element = self.xml_root.xpath(xpath, namespaces=Jazz.xpath_namespace())
        return func(element) if func is not None else element

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

        self.xml_root = self.jazz_client.get_xml(self.artifact_uri, op_name=self.op_name)
        self.init_from_xml_root()
        return self

    def update_from_xml_root(self):
        self.xpath_get_item("//dcterms:title").text = self.title if self.title is not None else ""
        self.xpath_get_item("//dcterms:description").text = self.description if self.description is not None else ''
        # self.xpath_get_item("//nav:parent/@rdf:resource", func=None)[0] = self.parent if self.parent is not None else ''
        self.xpath_get_item("//nav:parent", func=None)[0].set(self.jazz_client.resolve_name("rdf:resource"),
                                                              self.parent if self.parent is not None else '')

    def update_to_xml_root(self):
        pass

    def put(self) -> object:
        self.update_from_xml_root()
        text = etree.tostring(self.xml_root)
        etag = self.xml_root.attrib['ETag'] if 'ETag' in self.xml_root.attrib else None
        del self.xml_root.attrib['ETag']
        log.logger.debug(f"About to put {text}")

        def check_response(response):
            # log.logger.debug(f"Result was {response}")
            if response.status_code >= 400 and response.status_code <= 499:
                raise Exception(f"Result was {response}. Couldn't put artifact.")
            pass

        new_xml_root = self.jazz_client.put_xml(self.artifact_uri,
                                                data=text,
                                                if_match=etag,
                                                op_name=self.op_name,
                                                check=check_response)
        # FIXME: We get back the updated object, that data needs to be read into local state.
        if new_xml_root is None:
            #raise Exception("Invalid XML response from server")
            pass
        else:
            self.xml_root = new_xml_root
            # This is a problem, maybe.
            self.init_from_xml_root()

        return self

    def delete(self) -> object:
        self.update_from_xml_root()
        text = etree.tostring(self.xml_root)
        etag = self.xml_root.attrib['ETag'] if 'ETag' in self.xml_root.attrib else None
        del self.xml_root.attrib['ETag']
        log.logger.debug(f"About to delete {text}")

        def check_response(response):
            # log.logger.debug(f"Result was {response}")
            if response.status_code >= 400 and response.status_code <= 499:
                raise Exception(f"Result was {response}. Couldn't put artifact.")
            pass

        new_xml_root = self.jazz_client.delete_xml(self.artifact_uri,
                                                   if_match=etag,
                                                   op_name=self.op_name,
                                                   check=check_response)
        # FIXME: We get back the updated object, that data needs to be read into local state.
        if new_xml_root is None:
            #raise Exception("Invalid XML response from server")
            pass
        else:
            self.xml_root = new_xml_root
            # This is a problem, maybe.
            self.init_from_xml_root()

        return self


class RequirementCollection(DNGRequest):
    """
    <rdf:RDF xmlns:nav="http://jazz.net/ns/rm/navigation#" xmlns:rm_property="https://rtc-sbox.intel.com/rrc/types/"
         xmlns:acp="http://jazz.net/ns/acp#" xmlns:oslc_rm="http://open-services.net/ns/rm#"
         xmlns:oslc="http://open-services.net/ns/core#" xmlns:oslc_config="http://open-services.net/ns/config#"
         xmlns:oslc_auto="http://open-services.net/ns/auto#" xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:process="http://jazz.net/ns/process#" xmlns:jazz_rm="http://jazz.net/ns/rm#"
         xmlns:calm="http://jazz.net/xmlns/prod/jazz/calm/1.0/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rm="http://www.ibm.com/xmlns/rdm/rdf/" xmlns:public_rm_10="http://www.ibm.com/xmlns/rm/public/1.0/"
         xmlns:dng_task="http://jazz.net/ns/rm/dng/task#" xmlns:dcterms="http://purl.org/dc/terms/"
         xmlns:acc="http://open-services.net/ns/core/acc#">
        <rdf:Description rdf:about="https://rtc-sbox.intel.com/rrc/resources/_DNuDUxBUEeit3bw9wrTg3Q">
            <process:projectArea rdf:resource="https://rtc-sbox.intel.com/rrc/process/project-areas/_xf5p4XNnEeecjP8b5e9Miw"/>
            <nav:parent rdf:resource="https://rtc-sbox.intel.com/rrc/folders/_4p0zw_J4Eeec-bwG5--tlA"/>
            <dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-13T00:23:01.428Z
            </dcterms:created>
            <oslc:instanceShape rdf:resource="https://rtc-sbox.intel.com/rrc/types/_GeAbgnNoEeecjP8b5e9Miw"/>
            <dcterms:contributor rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
            <dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#string">247587</dcterms:identifier>
            <dcterms:creator rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
            <dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-27T00:16:37.354Z
            </dcterms:modified>
            <acp:accessControl rdf:resource="https://rtc-sbox.intel.com/rrc/accessControl/_xf5p4XNnEeecjP8b5e9Miw"/>
            <dcterms:title rdf:parseType="Literal">Test Collection</dcterms:title>
            <oslc:serviceProvider rdf:resource="https://rtc-sbox.intel.com/rrc/oslc_rm/_xf5p4XNnEeecjP8b5e9Miw/services.xml"/>
            <rdf:type rdf:resource="http://jazz.net/ns/rm#Collection"/>
            <oslc_rm:uses rdf:resource="https://rtc-sbox.intel.com/rrc/resources/_culds7S7EeeKve_VoIyffA"/>
            <oslc_config:component rdf:resource="https://rtc-sbox.intel.com/rrc/cm/component/_xv-GMHNnEeecjP8b5e9Miw"/>
            <oslc_rm:uses rdf:resource="https://rtc-sbox.intel.com/rrc/resources/_B0x7URHREeit3bw9wrTg3Q"/>
            <rdf:type rdf:resource="http://open-services.net/ns/rm#RequirementCollection"/>
            <oslc_rm:uses rdf:resource="https://rtc-sbox.intel.com/rrc/resources/_anNx4REbEeit3bw9wrTg3Q"/>
            <dcterms:description rdf:parseType="Literal">This is a new line.This is a new line.This is a new line.This is a
                new line.This is a new line.This is a new line.This is a new line.This is a new line.This is a new line.This
                is a new line.This is a new line.This is a new line.This is a new line.This is a new line.This is a new
                line.This is a new line.This is a new line.This is a new line.This is a new line.This is a new line.This is
                a new line.This is a new line.This is a new line.
            </dcterms:description>
        </rdf:Description>
    </rdf:RDF>
    """
    def __init__(self, jazz_client: object, artifact_uri: str=None, instance_shape: str=None,
                 title: str = None, description: str = None, parent: str = None, xml_root=None,
                 property_uri: str=None, op_name: str='RequirementCollection', **kwargs):
        super().__init__(jazz_client, artifact_uri=artifact_uri, title=title, description=description, parent=parent, xml_root=xml_root,
                         primary_list=['uri', 'title', 'identifier', 'type', 'description', 'subject', 'creator', 'modified'],
                         property_uri=property_uri, instance_shape=instance_shape,
                         resource_property_list=['primaryText'], op_name=op_name)

        for key in kwargs:
            self[key] = kwargs[key]

        self._requirements = None

    def update_from_xml_root(self):
        super().update_from_xml_root()

        # FIXME: Fill in the proper values!
        # self.xpath_get_item("//dcterms:title").text = self.title if self.title is not None else ""
        # self.xpath_get_item("//dcterms:description").text = self.description if self.description is not None else ''
        # self.xpath_get_item("//nav:parent/@rdf:resource", func=None)[0] = self.parent if self.parent is not None else ''
        # self.xpath_get_item("//nav:parent", func=None)[0].set(self.jazz_client.resolve_name("rdf:resource"),
        #
        #                                       self.parent if self.parent is not None else '')

    def update_to_xml_root(self):
        super().update_to_xml_root()
        requirements = self.requirement_set()
        # -- Remove existing uses elements
        description = self.xml_root.xpath("//rdf:Description", namespaces=Jazz.xpath_namespace())[0]
        for uses in self.xml_root.xpath("//oslc_rm:uses", namespaces=Jazz.xpath_namespace()):
            description.remove(uses)
        for resource in requirements:
            description.append(etree._Element("oslc_rm:uses", attrib={'rdf:resource': resource}))
        return etree.tostring(self.xml_root)

    def requirement_set(self):
        if self._requirements is None:
            self._requirements = set()
            for requirement_uri in self.xml_root.xpath("//oslc_rm:uses/@rdf:resource",
                                                       namespaces=Jazz.xpath_namespace()):
                self._requirements.add(requirement_uri)
            pass

        return self._requirements

    def add_requirements(self, uri_list: Iterable):
        self.requirement_set().union(set(uri_list))
        pass

    def remove_requirements(self, uri_list: Iterable):
        self.requirement_set().remove(set(uri_list))



Jazz.map_shape_name_to_class("Collection Release", RequirementCollection)


class GenericRequirement(DNGRequest):
    """Generic Requirement place holder class..."""
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
                         primary_list=[
                             'uri', 'title', 'identifier', 'type', 'description', 'subject',
                             'creator', 'modified',
                         ],
                         property_uri=property_uri, instance_shape=instance_shape,
                         resource_property_list=['primaryText'], op_name=op_name)

    def update_from_xml_root(self):
        super().update_from_xml_root()

        # FIXME: Fill in the proper values!
        # self.xpath_get_item("//dcterms:title").text = self.title if self.title is not None else ""
        # self.xpath_get_item("//dcterms:description").text = self.description if self.description is not None else ''
        # self.xpath_get_item("//nav:parent/@rdf:resource", func=None)[0] = self.parent if self.parent is not None else ''
        # self.xpath_get_item("//nav:parent", func=None)[0].set(self.jazz_client.resolve_name("rdf:resource"),
        #                                                       self.parent if self.parent is not None else '')


Jazz.map_shape_name_to_class("Generic Requirement", GenericRequirement)


class Requirement(GenericRequirement):

    def __init__(self, jazz_client: object, artifact_uri: str=None, instance_shape: str=None,
                 title: str = None, description: str = None, parent: str = None, xml_root=None,
                 property_uri: str=None, op_name: str=None, **kwargs):
        super().__init__(jazz_client, artifact_uri=artifact_uri, title=title, description=description,
                         parent=parent, xml_root=xml_root,
                         primary_list=[
                             'uri', 'title', 'identifier', 'type', 'description', 'subject',
                             'creator', 'modified',
                         ],
                         property_uri=property_uri, instance_shape=instance_shape,
                         resource_property_list=['primaryText'], op_name=op_name)

        for key in kwargs:
            self[key] = kwargs[key]

    @classmethod
    def create_requirement(cls, client: Jazz, name: str=None, description: str=None, parent_folder: object=None,
                           resource_type: str="http://open-services.net/ns/rm#Requirement",
                           op_name: str=None) -> object:
        client.logger.debug(f"create_requirement('{parent_folder.artifact_uri}')")
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

        # post_xml actually receives the returned content for the requested resource.
        response = None

        def get_response(resp):
            nonlocal response
            response = resp

        xml_response = client.post_xml(requirement_creation_factory, op_name=op_name, data=xml, check=get_response)

        if response.status_code not in [201]:
            raise PermissionError(f"Unable to create Requirement '{name}', result status {response.status_code}")

        return Requirement(client, xml_root=xml_response)


Jazz.map_shape_name_to_class("Default Requirement", Requirement)


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
                 title: str = None, description: str=None, parent: str=None, xml_root=None,
                 instance_shape: str=None, op_name: str=None):
        super().__init__(jazz_client, title=title, description=description, artifact_uri=folder_uri,
                         parent=parent, xml_root=xml_root, op_name=op_name)
        # self.artifact_uri = folder_uri
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
            self.subfolders_xml_root = self .jazz_client.get_xml(self.subfolders, op_name=self.op_name)

    def read(self, folder_uri: str) -> DNGRequest:
        self.artifact_uri = folder_uri
        self.xml_root = self.jazz_client.get_xml(self.artifact_uri, op_name=self.op_name)
        self.init_from_xml_root()
        return self

    def update_from_xml_root(self):
        super().update_from_xml_root()

        if self.component is not None:
            #self.xpath_get_item("//oslc_config:component/@rdf:resource", func=None)[0] = self.component
            self.xpath_get_item("//oslc_config:component", func=None)[0].set(self.jazz_client.resolve_name("rdf:resource"),
                                                                             self.component)

        if self.service_provider is not None:
            self.xpath_get_item("//oslc:serviceProvider/@rdf:resource", func=None)[0] = self.service_provider
            self.xpath_get_item("//oslc:serviceProvider", func=None)[0].set(self.jazz_client.resolve_name("rdf:resource"),
                                                                            self.service_provider)

    def get_folder_uri(self):
        return self.artifact_uri

    def get_root_folder_uri(self, op_name: str=None) -> str:
        folder_query_xpath = '//oslc:QueryCapability[dcterms:title="Folder Query Capability"]/oslc:queryBase/@rdf:resource'
        folder_query_uri = self.jazz_client.get_service_provider_root().xpath(folder_query_xpath,
                                                                              namespaces=Jazz.xpath_namespace())[0]
        folder_result_xml = self.jazz_client.get_xml(folder_query_uri, op_name=op_name)
        root_path_uri = folder_result_xml.xpath("//nav:folder[dcterms:title=\"root\"]/@rdf:about",
                                                namespaces=Jazz.xpath_namespace())[0]
        return root_path_uri

    def get_name(self, op_name=None) -> str:
        node = self.xml_root.xpath("//dcterms:title/text()", namespaces=Jazz.xpath_namespace())
        return node[0]

    def get_uri_of_matching_folders(self, path: str) -> list:
        name_list = []
        def get_subfolder_query(query: str):
            return self.jazz_client.get_xml(query, op_name=self.op_name)

        def get_subfolder_info(path: str, query: str) -> list:
            """Return a list of matching subfolders"""
            result_list = []
            split_path = path.split("/")
            subfolders_root = get_subfolder_query(query)
            subfolder_list = subfolders_root.xpath("//nav:folder", namespaces=Jazz.xpath_namespace())
            for candidate in subfolder_list:
                name = candidate.xpath(".//dcterms:title/text()", namespaces=Jazz.xpath_namespace())[0]
                if split_path[0]!=name:
                    continue

                sub_folder_query = candidate.xpath(".//nav:subfolders/@rdf:resource", namespaces=Jazz.xpath_namespace())[0]

                if len(split_path)>1:
                    result_list = result_list + get_subfolder_info(split_path[1], sub_folder_query)
                else:
                    # No more path left, if we get here this is it!
                    about = candidate.xpath("../nav:folder/@rdf:about", namespaces=Jazz.xpath_namespace())[0]
                    result_list.append(about)
                    name_list.append(name)

            return result_list

        current_folder = self
        if path.startswith("/"):
            current_folder = self.get_root_folder(self.jazz_client)
            path = path[1:]

        if not path:
            result_list = [current_folder.artifact_uri]
        else:
            result_list = get_subfolder_info(path, current_folder.subfolders)
        return result_list

    #
    #   -- This belongs in DNGRequest (Maybe not. See below)
    #
    def get_folder_artifacts(self, path: str="", name: str=None) -> list:
        parent_folder_uri_list = self.get_uri_of_matching_folders(path=path)

        parent_list = " ".join([f"<{uri}>" for uri in parent_folder_uri_list])
        # fixme: by quoting name here, we lose the ability to do wildcard searches and arbitrary queries. :-(
        title_clause = f' and dcterms:title="{name}"' if name is not None else ""
        # title_clause = f' and dcterms:title=*' if name is not None else ""
        xml_artifacts = self.jazz_client.query_xml(oslc_where=f"nav:parent in [{parent_list}]{title_clause}",
                                                   oslc_select="*")
        #
        # -- It might make sense here to return more information from the query. Collections appear
        #    to provide identical XML:
        #
        # ---------------------------------------------------------------------------
        # <rdfs:member>
        #     <oslc_rm:Requirement rdf:about="https://rtc-sbox.intel.com/rrc/resources/_iYQpMxBTEeit3bw9wrTg3Q">
        #         <rt:_ySe9YXNnEeecjP8b5e9Miw rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-13T00:19:21.059Z</rt:_ySe9YXNnEeecjP8b5e9Miw>
        #         <dcterms:description></dcterms:description>
        #         <oslc:instanceShape rdf:resource="https://rtc-sbox.intel.com/rrc/types/_DyURUXNoEeecjP8b5e9Miw"/>
        #         <jazz_rm:primaryText>PFH -- An Initial Requirement to play with</jazz_rm:primaryText> <!-- note: THE ONLY UNIQUE FIELD -->
        #         <dcterms:title>Copy of Copy of Copy of Copy of PFH -- An Initial Requirement to play with</dcterms:title>
        #         <rt:_yQ2lunNnEeecjP8b5e9Miw rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        #         <dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-13T00:19:21.059Z</dcterms:modified>
        #         <dcterms:creator rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        #         <dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-13T00:19:21.059Z</dcterms:created>
        #         <rt:_yX1-h3NnEeecjP8b5e9Miw rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-13T00:19:21.059Z</rt:_yX1-h3NnEeecjP8b5e9Miw>
        #         <f1:accessControl rdf:resource="https://rtc-sbox.intel.com/rrc/accessControl/_xf5p4XNnEeecjP8b5e9Miw"/>
        #         <nav:parent rdf:resource="https://rtc-sbox.intel.com/rrc/folders/_4p0zw_J4Eeec-bwG5--tlA"/>
        #         <dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">247584</dcterms:identifier>
        #         <rmTypes:ArtifactFormat rdf:resource="https://rtc-sbox.intel.com/rrc/types/_yBhwT3NnEeecjP8b5e9Miw#Text"/>
        #         <dcterms:contributor rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        #         <rt:_yUH8KXNnEeecjP8b5e9Miw rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        #     </oslc_rm:Requirement>
        # </rdfs:member>
        # <rdfs:member>
        #     <oslc_rm:RequirementCollection rdf:about="https://rtc-sbox.intel.com/rrc/resources/_FDZykRBUEeit3bw9wrTg3Q">
        #         <rt:_ySe9YXNnEeecjP8b5e9Miw rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-13T00:23:13.737Z</rt:_ySe9YXNnEeecjP8b5e9Miw>
        #         <dcterms:description></dcterms:description>
        #         <oslc:instanceShape rdf:resource="https://rtc-sbox.intel.com/rrc/types/_GeAbgnNoEeecjP8b5e9Miw"/>
        #         <dcterms:title>Copy of Copy of Test Collection</dcterms:title>
        #         <rt:_yQ2lunNnEeecjP8b5e9Miw rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        #         <dcterms:modified rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-13T00:23:13.737Z</dcterms:modified>
        #         <dcterms:creator rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        #         <dcterms:created rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-13T00:23:13.737Z</dcterms:created>
        #         <rt:_yX1-h3NnEeecjP8b5e9Miw rdf:datatype="http://www.w3.org/2001/XMLSchema#dateTime">2018-02-13T00:23:13.737Z</rt:_yX1-h3NnEeecjP8b5e9Miw>
        #         <f1:accessControl rdf:resource="https://rtc-sbox.intel.com/rrc/accessControl/_xf5p4XNnEeecjP8b5e9Miw"/>
        #         <nav:parent rdf:resource="https://rtc-sbox.intel.com/rrc/folders/_4p0zw_J4Eeec-bwG5--tlA"/>
        #         <dcterms:identifier rdf:datatype="http://www.w3.org/2001/XMLSchema#integer">247588</dcterms:identifier>
        #         <rmTypes:ArtifactFormat rdf:resource="https://rtc-sbox.intel.com/rrc/types/_yBhwT3NnEeecjP8b5e9Miw#Collection"/>
        #         <dcterms:contributor rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        #         <rt:_yUH8KXNnEeecjP8b5e9Miw rdf:resource="https://rtc-sbox.intel.com/jts/users/pfhanchx"/>
        #     </oslc_rm:RequirementCollection>
        # </rdfs:member>
        # ---------------------------------------------------------------------------
        n = Jazz.xpath_namespace()
        member = xml_artifacts.xpath("//rdfs:member/*", namespaces=Jazz.xpath_namespace())
        member_list = [etree.tostring(item) for item in member]
        artifact_uris = [uri for uri in xml_artifacts.xpath("//rdfs:member/*/@rdf:about", namespaces=Jazz.xpath_namespace())]
        return artifact_uris

    @classmethod
    def get_root_folder(cls, client: Jazz, op_name=None):
        if client.root_folder is None:
            folder_query_xpath = '//oslc:QueryCapability[dcterms:title="Folder Query Capability"]/oslc:queryBase/@rdf:resource'
            folder_query_uri = client.get_service_provider_root().xpath(folder_query_xpath, namespaces=Jazz.xpath_namespace())[0]

            folder_result_xml = client.get_xml(folder_query_uri, op_name=op_name)

            root_folder_xpath = "//nav:folder[dcterms:title=\"root\"]/@rdf:about"
            root_path_uri = folder_result_xml.xpath(root_folder_xpath, namespaces=Jazz.xpath_namespace())[0]
            client.root_folder = Folder(client, folder_uri=root_path_uri)

        # TODO: Return folder instead of URI
        return client.root_folder

    @classmethod
    def create_folder(cls, client: Jazz, name: str=None, parent_folder: str=None, op_name: str=None) -> object:
        client.logger.debug(f"create_folder('{name}')")

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

        xml_response = client.post_xml(folder_creation_factory, op_name=op_name, data=xml, check=get_response)

        if response.status_code not in [201]:
            raise PermissionError(f"Unable to create folder '{name}', result status {response.status_code}")

        return Folder(client, folder_uri=response.headers['location'])

# Note: Folder does not have an 'instanceShape'
Jazz.map_shape_name_to_class("folder", Folder)

