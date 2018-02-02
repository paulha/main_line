import unittest
from lxml import etree
from jazz.requirement import RequirementRequest

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


class Requirement_TestCases(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
