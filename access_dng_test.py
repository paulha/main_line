import unittest

import access_dng as ad
import urllib3
import utility_funcs.logger_yaml as log
import lxml as etree

# -- Login
urllib3.disable_warnings()
jazz = ad.Jazz(server_alias="sandbox", config_path=ad.JAZZ_CONFIG_PATH)

# -- DNG/One Android/Programs/Test Integration
# TEST_RECORD_1 = 67383               # 50161
# TEST_RECORD_2 = 67382               # 50162
TEST_RECORD_1 = jazz.jazz_config['TEST_RECORD_1']
TEST_RECORD_2 = jazz.jazz_config['TEST_RECORD_2']
SELECT_ALL = '*'
SELECT_ONE = "dcterms:identifier"
SELECT_TWO = "dcterms:title,dcterms:description"
WHERE_ALL = "*"
WHERE_ONE = f"dcterms:identifier={TEST_RECORD_1}"
WHERE_TWO = f"dcterms:identifier in [{TEST_RECORD_1},{TEST_RECORD_2}]"

PROJECT = 'Open Requirements Sandbox'


TEST_CREATE = True
TEST_QUERY = True


class Jazz_Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        urllib3.disable_warnings()
        super().setUpClass()
        cls.jazz = jazz

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        del cls.jazz



if TEST_QUERY:
    class TestQueryPrefix(Jazz_Test):
        def test_query_prefix_00(self):
            """Test with a single prefix"""
            query_result = self.jazz.query(
                oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
                oslc_select=SELECT_TWO
            )
            # todo: Check that the correct fields are returned
            self.assertIn('result', query_result, "Should have a result")
            self.assertGreater(len(query_result['Requirements']), 10, "Should be many results")
            self.assertIn('RequirementCollections', query_result, "Requirements collections should be returned")
            self.assertGreater(len(query_result['RequirementCollections']), 2, "Should be several collections")

        def test_query_prefix_01(self):
            """Test with two prefixes"""
            query_result = self.jazz.query(
                oslc_prefix='dcterms=<http://purl.org/dc/terms/>,oslc_rm=<http://open-services.net/ns/rm%23>',
                oslc_select=SELECT_TWO
            )
            # todo: Check that the correct fields are returned
            self.assertIn('result', query_result, "Should have a result")
            self.assertGreater(len(query_result['Requirements']), 10, "Should be many results")
            self.assertIn('RequirementCollections', query_result, "Requirements collections should be returned")
            self.assertGreater(len(query_result['RequirementCollections']), 2, "Should be several collections")

        def test_query_prefix_02(self):
            """Test with many prefixes"""
            query_result = self.jazz.query(
                oslc_prefix='rdf=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>,calm=<http://jazz.net/xmlns/prod/jazz/calm/1.0>,rm=<http://www.ibm.com/xmlns/rdm/rdf/>,oslc=<http://open-services.net/ns/core#>,jp10=<http://jazz.net/xmlns/prod/jazz/process/1.0/>,oslc_config=<http://open-services.net/ns/config#>,dcterms=<http://purl.org/dc/terms/>',
                oslc_select=SELECT_TWO
            )
            # todo: Check that the correct fields are returned
            self.assertIn('result', query_result, "Should have a result")
            self.assertGreater(len(query_result['Requirements']), 10, "Should be many results")
            self.assertIn('RequirementCollections', query_result, "Requirements collections should be returned")
            self.assertGreater(len(query_result['RequirementCollections']), 2, "Should be several collections")

        def test_query_prefix_03(self):
            """Test with (No) prefixes, defaults to namespaces list"""
            # fixme: This certainly won't work if the one above doesn't...
            self.jazz.add_namespace('dcterms', 'http://purl.org/dc/terms/')
            query_result = self.jazz.query(
                oslc_select=SELECT_TWO
            )
            # todo: Check that the correct fields are returned
            self.assertIn('result', query_result, "Should have a result")
            self.assertGreater(len(query_result['Requirements']), 10, "Should be many results")
            self.assertIn('RequirementCollections', query_result, "Requirements collections should be returned")
            self.assertGreater(len(query_result['RequirementCollections']), 2, "Should be several collections")


    class TestQuerySelect(Jazz_Test):
        def test_query_select_00(self):
            """Locate dcterms:identifier=67120, no selected fields (should return all)"""
            query_result = self.jazz.query(
                oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
                oslc_where=WHERE_ONE
            )
            # todo: Check that the correct fields are returned
            self.assertEqual("Query Results: 1", query_result['result'], "Should return only one record.")
            self.assertEqual(1, len(query_result['Requirements']), "Should be only one result")
            self.assertNotIn('RequirementCollections', query_result, "No requirements collections should be returned")

        def test_query_select_01(self):
            """Locate all (no where), return only dcterms:identifier"""
            query_result = self.jazz.query(
                oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
                oslc_select=SELECT_ONE,
            )
            # -- todo: This test should be improved to know that it's really returning (only) the field I asked for...
            self.assertGreater(len(query_result['Requirements']), 3, "Should be many results")
            # self.assertNotIn('RequirementCollections', query_result, "No requirements collections should be returned")

        def test_query_select_02(self):
            """Locate dcterms:identifier=67120, select all fields ('*')"""
            query_result = self.jazz.query(
                oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
                oslc_select=SELECT_ALL,
                oslc_where=WHERE_ONE
            )
            # todo: Check that the correct fields are returned
            self.assertEqual("Query Results: 1", query_result['result'], "Should return only one record.")
            self.assertEqual(1, len(query_result['Requirements']), "Should be only one result")
            self.assertNotIn('RequirementCollections', query_result, "No requirements collections should be returned")


    class TestQueryWhere(Jazz_Test):
        def test_query_where_03(self):
            """Locate dcterms:identifier in [{TEST_RECORD_1},{TEST_RECORD_2}], select all fields ('*')"""
            query_result = self.jazz.query(
                oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
                oslc_select='*',
                oslc_where=WHERE_TWO
            )
            # todo: Check that the correct fields are returned
            self.assertEqual("Query Results: 2", query_result['result'], "Should return two records.")
            self.assertEqual(2, len(query_result['Requirements']), "Should be two result")
            self.assertNotIn('RequirementCollections', query_result, "No requirements collections should be returned")

            result = self.jazz.read(query_result['Requirements'][0])
            pass

if TEST_CREATE:
    class TestCreateFolder(Jazz_Test):
        if True:
            def test_01_get_service_provider(self):
                self.assertEqual(self.jazz.get_service_provider(),
                                 "https://rtc-sbox.intel.com/rrc/oslc_rm/_xf5p4XNnEeecjP8b5e9Miw/services.xml",
                                 "get service provider URL")

            def test_02_get_root_folder(self):
                root = self.jazz.discover_root_folder()
                root_name = self.jazz.get_folder_name(root)
                self.assertEqual(root_name,
                                 "root",
                                 "discover root folder")


            def test_03_create_folder(self):
                PARENT_DELETE_ME = "parent_delete_me"
                parent = self.jazz.create_folder(PARENT_DELETE_ME)
                self.assertEqual(self.jazz.get_folder_name(parent),
                                 PARENT_DELETE_ME,
                                 "create a folder")

            def test_04_create_nested_folder(self):
                PARENT_NESTED_FOLDER = "parent_nested_folder"
                CHILD_FOLDER = "child_folder"
                parent = self.jazz.create_folder(PARENT_NESTED_FOLDER)
                child = self.jazz.create_folder(CHILD_FOLDER, parent_folder=parent)
                self.assertEqual(self.jazz.get_folder_name(child),
                                 CHILD_FOLDER,
                                 "create a child folder")

        def test_05_create_resource(self):
            resource = self.jazz.create_requirement()
            return




'''
""" This is not even close to how it needs to work, I'm afraid...
class TestUpdate(Jazz_Test):
    def test_update_00(self):
        """Locate dcterms:identifier={TEST_RECORD_1}, select all fields ('*')"""
        query_result = self.jazz.query(
            oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
            oslc_select='*',
            # This appears to work, but is very picky about formatting. :-(
            oslc_where=WHERE_ONE
        )
        # todo: Check that the correct fields are returned
        self.assertEqual("Query Results: 1", query_result['result'], "Should return two records.")
        self.assertEqual(1, len(query_result['Requirements']), "Should be two result")
        self.assertNotIn('RequirementCollections', query_result, "No requirements collections should be returned")

        description = query_result['query_root'].xpath(".//dcterms:description",  namespaces={'dcterms': "http://purl.org/dc/terms/"})
        pass
'''

if __name__ == '__main__':
    unittest.main()
    jazz.close()
    log.logger.info("Done")

