
import lxml as etree
import re
import datetime
from datetime import date
import utility_funcs.logger_yaml as log

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
