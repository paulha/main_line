import unittest

import access_dng as ad
import urllib3

TEST_RECORD = 50161
SELECT_ALL = '*'
SELECT_ONE = "dcterms:identifier"
SELECT_TWO = "dcterms:title,dcterms:description"
WHERE_ALL = "*"
WHERE_ONE = f"dcterms:identifier={TEST_RECORD}"

class QueryTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        urllib3.disable_warnings()
        cls.jazz = ad.Jazz(server_alias="dng", config_path=ad.JAZZ_CONFIG_PATH)

    @classmethod
    def tearDownClass(cls):
        cls.jazz.close()

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
            # oslc_prefix='rdf=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>,calm=<http://jazz.net/xmlns/prod/jazz/calm/1.0>,rm=<http://www.ibm.com/xmlns/rdm/rdf/>,oslc=<http://open-services.net/ns/core#>,jp10=<http://jazz.net/xmlns/prod/jazz/process/1.0/>,oslc_config=<http://open-services.net/ns/config#>,dcterms=<http://purl.org/dc/terms/>',
            oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
            # Note: Select "dcterms:identifier" field only in result
            oslc_select=SELECT_ONE,
        )
        # -- todo: This test should be improved to know that it's really returning (only) the field I asked for...
        self.assertGreater(len(query_result['Requirements']), 3, "Should be many results")
        # self.assertNotIn('RequirementCollections', query_result, "No requirements collections should be returned")

    def test_query_select_02(self):
        """Locate dcterms:identifier=67120, select all fields ('*')"""
        query_result = self.jazz.query(
            # oslc_prefix='rdf=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>,calm=<http://jazz.net/xmlns/prod/jazz/calm/1.0>,rm=<http://www.ibm.com/xmlns/rdm/rdf/>,oslc=<http://open-services.net/ns/core#>,jp10=<http://jazz.net/xmlns/prod/jazz/process/1.0/>,oslc_config=<http://open-services.net/ns/config#>,dcterms=<http://purl.org/dc/terms/>',
            oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
            # oslc_prefix='dcterms=<http://purl.org/dc/terms/>,rdf=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>,oslc=<http://open-services.net/ns/core#>,calm=<http://jazz.net/xmlns/prod/jazz/calm/1.0>,rm=<http://www.ibm.com/xmlns/rdm/rdf/>,oslc_config=<http://open-services.net/ns/config#,jp10=<http://jazz.net/xmlns/prod/jazz/process/1.0/>',
            # Note: Return "all" the fields...
            oslc_select=SELECT_ALL,
            oslc_where=WHERE_ONE
        )
        # todo: Check that the correct fields are returned
        self.assertEqual(query_result['result'], "Query Results: 1", "Should return only one record.")
        self.assertEqual(len(query_result['Requirements']), 1, "Should be only one result")
        self.assertNotIn('RequirementCollections', query_result, "No requirements collections should be returned")

    def test_query_select_03(self):
        """Locate dcterms:identifier=67120, select all fields ('*')"""
        query_result = self.jazz.query(
            oslc_prefix='dcterms=<http://purl.org/dc/terms/>',
            # Note: Return "all" the fields...
            oslc_select='*',
            oslc_where='dcterms:identifier=50161,dcterms:identifier=50162'
        )
        # todo: Check that the correct fields are returned
        self.assertEqual(query_result['result'], "Query Results: 1", "Should return only one record.")
        self.assertEqual(len(query_result['Requirements']), 1, "Should be only one result")
        self.assertNotIn('RequirementCollections', query_result, "No requirements collections should be returned")


if __name__ == '__main__':
    unittest.main()
    exit(0)
