from main_line import *
import urllib3
import sys
import regex as re

from jazz_dng_client import *
from lxml import etree

import pickle


def tos( element ):
    return etree.tostring(element, xml_declaration=True)


def get_requirement_as_dict(item) -> dict:
    return {
        'NAME':  item.get_name(),
        # This sort of bothers me, what if the original is poorly formatted XML?
        'PRIMARY_TEXT': etree.tostring(item.primary_text, xml_declaration=True) if item.primary_text is not None else '',
        'DNGID': item.get_identifier(),
        'URI':   item.artifact_uri,
        'EXTERNAL': str(item.external_system_id()).strip() if item.external_system_id() is not None else "",
        'KEY':   None,
        'GID':   None,
    }


def get_catalog(config, log):
    environment = config['DNG_Catalog']
    jazz_client = Jazz(environment['jazz_server'], JAZZ_CONFIG_PATH)
    catalog_folders, catalog_artifacts = jazz_client.find_requirements(environment['catalog_paths'])
    lookup = {x.get_identifier(): get_requirement_as_dict(x) for x in catalog_artifacts}
    requirement = lookup['50161']
    ext_id = requirement['EXTERNAL']
    requirement_by_dngid = {}
    requirement_by_jirakey = {}
    requirement_by_gid = {}
    jira_key_regex = r"^[A-Za-z]+-\d+"
    is_jira_key = re.compile(jira_key_regex)
    gid_regex = r"^\d+-\d+"
    is_gid = re.compile(gid_regex)
    for dngid, requirement in lookup.items():
        # dngid = requirement['DNGID']
        key = str(requirement['EXTERNAL'])
        requirement['KEY'] = key if re.search(jira_key_regex, key) else None
        requirement['GID'] = key if re.search(gid_regex, key) else None

        requirement_by_dngid[dngid] = requirement

        if requirement['KEY'] is not None:
            # Duplicates check?
            requirement_by_jirakey[key] = requirement

        if requirement['GID'] is not None:
            # Duplicates check?
            requirement_by_gid[key] = requirement


    with open(environment['pickle_file'], 'wb') as f:
        log.logger.info(f"Writing Requirements by DNG ID to picklefile '{environment['pickle_file']}'")
        pickle.dump(requirement_by_dngid, f)
        log.logger.info(f"Writing Requirements by JAMA GID to picklefile '{environment['pickle_file']}'")
        pickle.dump(requirement_by_gid, f)
        log.logger.info(f"Writing Requirements by Jira KEY to picklefile '{environment['pickle_file']}'")
        pickle.dump(requirement_by_jirakey, f)


if __name__ == "__main__":
    exit(mainline(get_catalog))

