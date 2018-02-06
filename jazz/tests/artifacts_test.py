import unittest
from lxml import etree
from .dng_test import JazzTest
from jazz.artifacts import RequirementRequest, Folder

sample = """
<rdf:RDF
        xmlns:oslc_rm="http://open-services.net/ns/rm#"
        xmlns:dc="http://purl.org/dc/terms/"
        xmlns:oslc="http://open-services.net/ns/core#"
        xmlns:nav="http://jazz.net/ns/rm/navigation#"
        xmlns:rm_property="http://rtc-sbox.intel.com/rrc/types/"
        xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <oslc_rm:Requirement
            xmlns:rm_jazz="http://jazz.net/ns/rm#"
            rdf:about="">
        <dc:title>MyDocument</dc:title>
        <dc:description>This is a test document
        and this is a second line</dc:description>
        <oslc:instanceShape rdf:resource="https://rtc-sbox.intel.com/rrc/types/_HtvlEXNoEeecjP8b5e9Miw"/>
        <nav:parent
                rdf:resource="https://rtc-sbox.intel.com/rrc/folders?projectURL=http://rtc-sbox.intel.com/rrc/process/project-areas/_xf5p4XNnEeecjP8b5e9Miw"/>
        <rm_jazz:primaryText rdf:parseType="Literal">
            <div xmlns="http://www.w3.org/1999/xhtml" id="_Nf2cQJKNEd25PMUBGiN3Dw">
                <h1 id="_DwpWsMueEd28xKN9fhQheA">Test Document</h1>
            </div>
        </rm_jazz:primaryText>
    </oslc_rm:Requirement>
</rdf:RDF>
"""


class RequirementTestCases(JazzTest):
    def test_01_requirement_get(self):
        r = RequirementRequest(property_uri='property', instanceShape='shape', parent='parent',
                               description="This is some description")
        self.assertEqual(r.property_uri, 'property')
        self.assertEqual(r.instanceShape, 'shape')
        self.assertEqual(r.parent, 'parent')
        self.assertEqual(r['description'], 'This is some description')

    def test_02_requirement_set(self):
        r = RequirementRequest(property_uri='property', instanceShape='shape', parent='parent')
        r.property_url = 'property'
        r.instance_shape = 'shape'
        r.parent_folder = 'parent'
        r['description'] = 'This is some description'
        self.assertEqual(r.property_uri, 'property')
        self.assertEqual(r.instanceShape, 'shape')
        self.assertEqual(r.parent, 'parent')
        self.assertEqual(r['description'], 'This is some description')

    def test_03_requirement_read(self):
        root = etree.fromstring(sample)
        r = RequirementRequest(property_uri='property', instanceShape='shape', parent='parent')
        r.initialize_from_xml(root)

class FolderTestcases(JazzTest):
    def test_01_read_folder(self):
        root_folder_uri = self.jazz.discover_root_folder()
        root_folder = Folder(self.jazz)
        result = root_folder.read(root_folder_uri)
        self.assertEqual(root_folder, result, "Call to read() did not return self")
        pass

class FindFolderTestCases(JazzTest):
    def test_01_find_empty_path(self):
        fs_finder = Folder(self.jazz)
        found = fs_finder.get_matching_folder_uri("")
        self.assertEqual([], found, "Empty path should return None")

    def test_10_find_top_dir_path(self):
        fs_finder = Folder(self.jazz)
        found = fs_finder.get_matching_folder_uri("pfh -- NewFolder")
        self.assertGreater(len(found), 0, "one or more found paths")
        folders = [self.jazz._get_xml(uri, op_name='read folders') for uri in found]
        pass

    def test_20_find_top_dir_path(self):
        fs_finder = Folder(self.jazz)
        found = fs_finder.get_matching_folder_uri("pfh -- NewFolder/subfolder to pff")
        self.assertGreater(len(found), 0, "one or more found paths")
        folders = self.jazz._get_xml(found[0], op_name='read folders')
        about = folders.xpath(".//nav:folder/@rdf:about", namespaces=fs_finder.xpath_namespaces())[0]
        resources = self.jazz._get_xml(about, op_name='read folders')
        provdr = folders.xpath(".//oslc:serviceProvider/@rdf:resource", namespaces=fs_finder.xpath_namespaces())[0]
        provider = self.jazz._get_xml(provdr, op_name='read folders')
        folder_query_xpath = '//oslc:QueryCapability[dcterms:title="Folder Query Capability"]/oslc:queryBase/@rdf:resource'
        folder_query = provider.xpath(folder_query_xpath,
                                      namespaces=fs_finder.xpath_namespaces())
        x = self.jazz._get_xml(folder_query[0], op_name='read folders')

        """
        To find the resources in a folder, find the ID of the folder and then find all the resources
        that have that ID as a parent.
        """

        pass




if __name__ == '__main__':
    unittest.main()
