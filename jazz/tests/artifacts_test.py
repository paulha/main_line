import unittest
from lxml import etree
from .dng_test import JazzTest, jazz, SERVICE_PROVIDER_URL
from jazz.artifacts import Requirement, RequirementCollection, Folder
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
    if 'RequirementTestCases' not in jazz.jazz_config:
        def test_01_requirement_get(self):
            r = Requirement(self.jazz, artifact_uri='artifact', instance_shape='shape', parent='parent',
                            property_uri='property', description="This is some description",
                            op_name='RequirementTestCases')
            self.assertEqual(r.artifact_uri, 'artifact')
            self.assertEqual(r.property_uri, 'property')
            self.assertEqual(r.instanceShape, 'shape')
            self.assertEqual(r.parent, 'parent')
            self.assertEqual(r['description'], 'This is some description')

        def test_02_requirement_set(self):
            r = Requirement(self.jazz, artifact_uri='artifact', property_uri='property', instance_shape='shape',
                            parent='parent', op_name='RequirementTestCases')
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
            r = Requirement(self.jazz, artifact_uri='property', instance_shape='shape',
                            parent='parent', op_name='RequirementTestCases')
            r.initialize_from_xml(root)

class FolderTestCases(JazzTest):
    if 'FolderTestcases' not in jazz.jazz_config:
        def test_01_read_folder(self):
            root_folder = Folder(self.jazz, op_name='FolderTestCases')
            result = root_folder.read(root_folder.artifact_uri)
            self.assertEqual(root_folder, result, "Call to read() did not return self")
            pass

class FindFolderTestCases(JazzTest):
    if 'FindFolderTestCases' not in jazz.jazz_config:
        def test_01_find_empty_path(self):
            fs_finder = Folder(self.jazz, op_name='FindFolderTestCases')
            found = fs_finder.get_uri_of_matching_folder("")
            self.assertEqual([], found, "Empty path should return None")

        def test_10_find_top_dir_path(self):
            search_path = self.jazz.jazz_config['DIRECTORY_1']
            fs_finder = Folder(self.jazz, op_name='FindFolderTestCases')
            found = fs_finder.get_uri_of_matching_folder(search_path)
            self.assertGreater(len(found), 0, "one or more found paths")
            folders = [self.jazz.get_xml(uri, op_name='read folders') for uri in found]
            expected_name = search_path.split('/')[-1]
            for folder in folders:
                found_name = folder.xpath("//dcterms:title/text()", namespaces=Jazz.xpath_namespace())[0]
                self.assertEqual(expected_name, found_name, "Expected and found name should be the same")

        def test_20_find_top_dir_path(self):
            search_path = self.jazz.jazz_config['DIRECTORY_2']
            fs_finder = Folder(self.jazz, op_name='FindFolderTestCases')
            found = fs_finder.get_uri_of_matching_folder(search_path)
            self.assertGreater(len(found), 0, "one or more found paths")
            folders = [self.jazz.get_xml(uri, op_name='read folders') for uri in found]
            expected_name = search_path.split('/')[-1]
            for folder in folders:
                found_name = folder.xpath("//dcterms:title/text()", namespaces=Jazz.xpath_namespace())[0]
                self.assertEqual(expected_name, found_name, "Expected and found name should be the same")
            pass


class FindResourcesTestCases(JazzTest):
    if 'FindResourcesTestCases' not in jazz.jazz_config:
        def test_20_get_folder_artifacts(self):
            """
            To find the resources in a folder, find the ID of the folder and then find all the resources
            that have that ID as a parent.
            """
            search_path = self.jazz.jazz_config['DIRECTORY_2']
            root = Folder(self.jazz, op_name='FindResourcesTestCases')
            found_resources = root.get_folder_artifacts(path=search_path)
            self.assertEqual(3, len(found_resources['Requirements']), "Should find 3 requirements")
            self.assertEqual(2, len(found_resources['RequirementCollections']), "Should find 2 requirements collections")
            pass

        def test_30_get_folder_requirements(self):
            """
            To find the resources in a folder, find the ID of the folder and then find all the resources
            that have that ID as a parent.
            """
            search_path = self.jazz.jazz_config['DIRECTORY_2']
            search_name = self.jazz.jazz_config['TEST_REQUIREMENT_1']
            root = Folder(self.jazz, op_name='FindResourcesTestCases')
            found_resources = root.get_folder_artifacts(path=search_path, name=search_name)
            self.assertEqual(1, len(found_resources['Requirements']), "Should find 1 requirements")
            self.assertNotIn('RequirementCollections', found_resources, "Should find NO requirement collection")
            pass

        def test_40_get_folder_collectiions(self):
            """
            To find the resources in a folder, find the ID of the folder and then find all the resources
            that have that ID as a parent.
            """
            search_path = self.jazz.jazz_config['DIRECTORY_2']
            search_name = self.jazz.jazz_config['TEST_REQUIREMENT_COLLECTION_1']
            root = Folder(self.jazz, op_name='FindResourcesTestCases')
            found_resources = root.get_folder_artifacts(path=search_path, name=search_name)
            self.assertNotIn('Requirements', found_resources, "Should find NO requirements")
            self.assertEqual(1, len(found_resources['RequirementCollections']), "Should find 1 requirement collection")
            pass


class ResourceUpdateTestCases(JazzTest):
    if 'ResourceUpdateTestCases' not in jazz.jazz_config:
        def test_10_update_requirement_description(self):
            search_path = self.jazz.jazz_config['DIRECTORY_2']
            fs_finder = Folder(self.jazz, op_name='FindResourcesTestCases')
            found_resources = fs_finder.get_folder_artifacts(search_path)
            self.assertGreater(len(found_resources['Requirements']), 0, "Should find at least one requirement...")

            requirement = Requirement(self.jazz, artifact_uri=found_resources['Requirements'][0], op_name='ResourceUpdateTestCases')
            requirement.get()

            text = requirement.description + "\n" if requirement.description is not None else ""
            assigned_text = text + "This is a new line."
            requirement.description = assigned_text

            response = requirement.put()

            result_requirement = Requirement(self.jazz, artifact_uri=found_resources['Requirements'][0],
                                             op_name='ResourceUpdateTestCases')
            result_requirement.get()

            found_text = result_requirement.description if result_requirement.description is not None else ""

            self.assertEqual(assigned_text, found_text, 'Description from updated and re-read nodes should be equal')
            pass

        def test_20_update_collection_description(self):
            search_path = self.jazz.jazz_config['DIRECTORY_2']
            fs_finder = Folder(self.jazz, op_name='FindResourcesTestCases')
            found_resources = fs_finder.get_folder_artifacts(search_path)
            self.assertGreater(len(found_resources['RequirementCollections']), 0, "Should find at least one Requirement Collection...")

            requirement = RequirementCollection(self.jazz, artifact_uri=found_resources['RequirementCollections'][0],
                                                op_name='ResourceUpdateTestCases')
            requirement.get()

            requirement.get()

            text = requirement.description + "\n" if requirement.description is not None else ""
            assigned_text = text + "This is a new line."
            requirement.description = assigned_text

            response = requirement.put()

            result_requirement = RequirementCollection(self.jazz, artifact_uri=found_resources['RequirementCollections'][0],
                                                       op_name='ResourceUpdateTestCases')
            result_requirement.get()

            found_text = result_requirement.description if result_requirement.description is not None else ""

            self.assertEqual(assigned_text, found_text, 'Description from updated and re-read collections should be equal')
            pass


class TestCreateFolder(JazzTest):
    if 'TestCreateFolder' not in jazz.jazz_config:
        def test_01_get_service_provider(self):
            self.assertEqual(SERVICE_PROVIDER_URL,
                             self.jazz.get_service_provider(),
                             "get service provider URL")

        def test_02_get_root_folder(self):
            root_folder = Folder.get_root_folder(self.jazz, op_name='TestCreateFolder')
            root_name = root_folder.get_name()
            self.assertEqual("root",
                             root_name,
                             "discover root folder")

        def test_03_create_folder(self):
            PARENT_DELETE_ME = "parent_delete_me"
            parent = Folder.create_folder(self.jazz, name=PARENT_DELETE_ME, op_name='TestCreateFolder')
            self.assertEqual(PARENT_DELETE_ME,
                             parent.get_name(),
                             "DNG doesn't agree about folder name")
            self.assertEqual(PARENT_DELETE_ME,
                             parent.title,
                             "Folder disagrees about it's name")

        def test_04_create_nested_folder(self):
            PARENT_NESTED_FOLDER = "parent_nested_folder"
            CHILD_FOLDER = "child_folder"
            parent = Folder.create_folder(self.jazz, name=PARENT_NESTED_FOLDER, op_name='TestCreateFolder')
            child = Folder.create_folder(self.jazz, name=CHILD_FOLDER, parent_folder=parent)
            self.assertEqual(CHILD_FOLDER,
                             child.get_name(),
                             "create a child folder")

        def test_05_create_resource(self):
            name = self.jazz.jazz_config['TEST_REQUIREMENT_1']
            created = Requirement.create_requirement(self.jazz,
                                                     name=name,
                                                     description="Here is some description!",
                                                     parent_folder=Folder.get_root_folder(self.jazz),
                                                     op_name = 'TestCreateFolder')

            # At this point, the resource has been created but we have to read it to have a local copy...
            # created = RequirementRequest(self.jazz, artifact_uri=uri)
            created.get()
            s = etree.tostring(created.xml_root)
            return


class ZendOfTesting(JazzTest):
    def test_10_remove_parent_delete_me(self):
        target_uri_list = Folder(self.jazz).get_uri_of_matching_folder("parent_delete_me")
        for uri in target_uri_list:
            folder = Folder(self.jazz, folder_uri=uri)
            folder.delete()
            pass

    def test_20_remove_parent_nested_folder(self):
        target_uri_list = Folder(self.jazz).get_uri_of_matching_folder("parent_nested_folder")
        for uri in target_uri_list:
            folder = Folder(self.jazz, folder_uri=uri)
            folder.delete()
            pass

    def test_30_remove_parent_nested_folder(self):
        target_uri_list = Folder(self.jazz).get_folder_artifacts(path="/", name="Test Data")
        for uri in target_uri_list:
            requirement = Requirement(self.jazz, folder_uri=uri)
            name = requirement.get_name()
            requirement.delete()
            pass

class FolderAndArtifactLookups(JazzTest):
    def test_10_get_root_folder_by_name(self):
        """Look up root folder using "/" as the name."""
        root_folder_uri = Folder(self.jazz).get_root_folder_uri()
        root_by_name_uri = Folder(self.jazz).get_uri_of_matching_folder("/")
        self.assertIn(root_folder_uri, root_by_name_uri, "Finding root folder by name '/' did not match uri's")

    def test_20_get_root_folder_by_empty_name(self):
        """Look up root folder using "" as the name."""
        root_folder_uri = Folder(self.jazz).get_root_folder_uri()
        root_by_name_uri = Folder(self.jazz).get_uri_of_matching_folder("")
        self.assertIn(root_folder_uri, root_by_name_uri, "Finding root folder by name '' did not match uri's")

    def test_30_get_About_folder_by_name(self):
        """Look up About folder using "About" as the name."""
        root_folder_uri = Folder(self.jazz).get_root_folder_uri()
        about_by_name_uri = Folder(self.jazz).get_uri_of_matching_folder("About")
        about_folder = Folder(self.jazz, folder_uri=about_by_name_uri)
        self.assertEqual("About", about_folder.get_name(), "Did not get correct name for About folder")

    def test_40_get_About_folder_by_rooted_name(self):
        """Look up About folder using "/About" as the name."""
        root_folder_uri = Folder(self.jazz).get_root_folder_uri()
        about_by_name_uri = Folder(self.jazz).get_uri_of_matching_folder("/About")
        about_folder = Folder(self.jazz, folder_uri=about_by_name_uri)
        self.assertEqual("About", about_folder.get_name(), "Did not get correct name for 'About' folder")

    def test_50_get_About_User_Guide_artifacts_folder_by_rooted_name(self):
        """Look up About folder using "/About/User Guide artifacts" as the name."""
        root_folder_uri = Folder(self.jazz).get_root_folder_uri()
        about_by_name_uri = Folder(self.jazz).get_uri_of_matching_folder("/About/User Guide artifacts")
        about_folder = Folder(self.jazz, folder_uri=about_by_name_uri)
        self.assertEqual("User Guide artifacts", about_folder.get_name(),
                         "Did not get 'User Guide artifacts' name for 'User Guide artifacts' folder")

    def test_51_get_About_User_Guide_artifacts_folder_by_rooted_name(self):
        """Look up About folder using "/About/User Guide artifacts/" as the name."""
        root_folder_uri = Folder(self.jazz).get_root_folder_uri()
        about_by_name_uri = Folder(self.jazz).get_uri_of_matching_folder("/About/User Guide artifacts/")
        about_folder = Folder(self.jazz, folder_uri=about_by_name_uri)
        self.assertEqual("User Guide artifacts", about_folder.get_name(),
                         "Did not get 'User Guide artifacts' name for 'User Guide artifacts' folder")

    def test_110_get_root_artifacts(self):
        f = Folder(self.jazz)
        result_list = f.get_folder_artifacts()
        # results are divided by <rdfs:member>
        #for uri in result_list:
        #    f.get_object_from_uri(uri, "GetObjectFromUri")
        pass

    def test_120_get_folder_artifacts(self):
        f = Folder(self.jazz)
        result_list = f.get_folder_artifacts(path="Z: PFH -- Test Content/subfolder or Z: PFH -- Test Content", name="Test Collection")
        # results are divided by <rdfs:member>
        #for uri in result_list:
        #    f.get_object_from_uri(uri, "GetObjectFromUri")
        xml = self.jazz.get_xml(result_list[0])
        shape_uri = xml.xpath("//oslc:instanceShape/@rdf:resource", namespaces=self.jazz.xpath_namespace())
        shape_xml = self.jazz.get_xml(shape_uri[0])
        pass

    def test_130_get_folder_artifacts(self):
        f = Folder(self.jazz)
        result_list = f.get_folder_artifacts(path="Z: PFH -- Test Content/subfolder or Z: PFH -- Test Content", name="Test Collection")
        # results are divided by <rdfs:member>
        #for uri in result_list:
        #    f.get_object_from_uri(uri, "GetObjectFromUri")
        xml = self.jazz.get_xml(result_list[0])
        shape_uri = xml.xpath("//oslc:instanceShape/@rdf:resource", namespaces=self.jazz.xpath_namespace())
        result = f.get_shape_info(shape_uri[0])
        shape_xml = self.jazz.get_xml(shape_uri[0])
        title = shape_xml.xpath("//oslc:ResourceShape/dcterms:title/text()", namespaces=self.jazz.xpath_namespace())
        pass


if __name__ == '__main__':
    unittest.main()


