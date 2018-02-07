import unittest
from lxml import etree
from .dng_test import JazzTest
from jazz.artifacts import RequirementRequest, RequirementCollection, Folder
from jazz.dng import Jazz

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
        r = RequirementRequest(self.jazz, artifact_uri='artifact', instance_shape='shape', parent='parent',
                               property_uri='property', description="This is some description")
        self.assertEqual(r.artifact_uri, 'artifact')
        self.assertEqual(r.property_uri, 'property')
        self.assertEqual(r.instanceShape, 'shape')
        self.assertEqual(r.parent, 'parent')
        self.assertEqual(r['description'], 'This is some description')

    def test_02_requirement_set(self):
        r = RequirementRequest(self.jazz, artifact_uri='artifact', property_uri='property', instance_shape='shape', parent='parent')
        r.property_url = 'property'
        r.instance_shape = 'shape'
        r.parent_folder = 'parent'
        r['description'] = 'This is some description'
        self.assertEqual(r.artifact_uri, 'artifact')
        self.assertEqual(r.property_uri, 'property')
        self.assertEqual(r.instanceShape, 'shape')
        self.assertEqual(r.parent, 'parent')
        self.assertEqual(r['description'], 'This is some description')

    def test_03_requirement_read(self):
        root = etree.fromstring(sample)
        r = RequirementRequest(self.jazz, artifact_uri='property', instance_shape='shape', parent='parent')
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
        search_path = self.jazz.jazz_config['DIRECTORY_1']
        fs_finder = Folder(self.jazz)
        found = fs_finder.get_matching_folder_uri(search_path)
        self.assertGreater(len(found), 0, "one or more found paths")
        folders = [self.jazz._get_xml(uri, op_name='read folders') for uri in found]
        expected_name = search_path.split('/')[-1]
        for folder in folders:
            found_name = folder.xpath("//dcterms:title/text()", namespaces=Jazz.xpath_namespace())[0]
            self.assertEqual(expected_name, found_name, "Expected and found name should be the same")

    def test_20_find_top_dir_path(self):
        search_path = self.jazz.jazz_config['DIRECTORY_2']
        fs_finder = Folder(self.jazz)
        found = fs_finder.get_matching_folder_uri(search_path)
        self.assertGreater(len(found), 0, "one or more found paths")
        folders = [self.jazz._get_xml(uri, op_name='read folders') for uri in found]
        expected_name = search_path.split('/')[-1]
        for folder in folders:
            found_name = folder.xpath("//dcterms:title/text()", namespaces=Jazz.xpath_namespace())[0]
            self.assertEqual(expected_name, found_name, "Expected and found name should be the same")
        pass


if True:
    class FindResourcesTestCases(JazzTest):
        def test_20_get_folder_artifacts(self):
            """
            To find the resources in a folder, find the ID of the folder and then find all the resources
            that have that ID as a parent.
            """
            search_path = self.jazz.jazz_config['DIRECTORY_2']
            fs_finder = Folder(self.jazz)
            found_resources = fs_finder.get_folder_artifacts(search_path)
            self.assertEqual(3, len(found_resources['Requirements']), "Should find 3 requirements")
            self.assertEqual(2, len(found_resources['RequirementCollections']), "Should find 3 requirements")

            requirement = RequirementRequest(self.jazz, found_resources['Requirements'][0], op_name='FindResourcesTestCases')
            requirement.get()
            requirement_collection = RequirementCollection(self.jazz, found_resources['RequirementCollections'][0], op_name='FindResourcesTestCases')
            requirement_collection.get()
            pass


if __name__ == '__main__':
    unittest.main()
