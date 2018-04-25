from lxml import etree

namespaces = {
    'nav': "http://jazz.net/ns/rm/navigation#",
    'acp': "http://jazz.net/ns/acp#",
    'oslc_rm': "http://open-services.net/ns/rm#",
    'oslc': "http://open-services.net/ns/core#",
    'rm_property': "https://rtc.intel.com/dng0001001/types/",
    'oslc_config': "http://open-services.net/ns/config#",
    'oslc_auto': "http://open-services.net/ns/auto#",
    'dc': "http://purl.org/dc/elements/1.1/",
    'process': "http://jazz.net/ns/process#",
    'jazz_rm': "http://jazz.net/ns/rm#",
    'calm': "http://jazz.net/xmlns/prod/jazz/calm/1.0/",
    'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    'rm': "http://www.ibm.com/xmlns/rdm/rdf/",
    'public_rm_10': "http://www.ibm.com/xmlns/rm/public/1.0/",
    'dng_task': "http://jazz.net/ns/rm/dng/task#",
    'j.0': "http://www.ibm.com/xmlns/rdm/types/",
    'dcterms': "http://purl.org/dc/terms/",
    'acc': "http://open-services.net/ns/core/acc#",
}

root = etree.parse("Requirement2.xml")

title = root.xpath("//dcterms:title/text()", namespaces=namespaces)
# -- Note: This works, here!
id_list = root.xpath("//rm_property:_5cTORK_4EeekDP1y4xXYPQ/text()", namespaces=namespaces)
pass
