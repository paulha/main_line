from main_line import *
import urllib3
import sys
import regex as re

from jazz_dng_client import *
from lxml import etree

import pickle


def tos( element ):
    return etree.tostring(element, xml_declaration=True)


def traverse_path(jazz_client: Jazz, path: str, base_folder: Folder=None, folder_separator: str="/") -> Folder :
    split_path = path.split(folder_separator)
    base = Folder(jazz_client).get_root_folder(jazz_client) if base_folder is None else base_folder
    for folder_name in split_path:
        base_uri_list = base.get_uri_of_matching_folders(folder_name)
        if len(base_uri_list)==0:
            # -- No match found
            return []

        # -- Note that in Jazz, duplicate names on the same level are actually allowed!
        base = Folder(jazz_client, folder_uri=base_uri_list[0])

    return base


def get_all_subfolders(jazz_client: Jazz, folder: Folder, path: str=None) -> list:
    """Return all subordinate folders"""
    log.logger.debug(f"Checking {folder}...")

    result_list = []
    subfolders_root = folder.get_subfolder_query(folder.subfolders)
    subfolder_uri_list = subfolders_root.xpath("//nav:folder/@rdf:about", namespaces=Jazz.xpath_namespace())
    if len(subfolder_uri_list)>0:
        for sub_folder_uri in subfolder_uri_list:
            sub_folder = Folder(jazz_client, folder_uri=sub_folder_uri)
            result_list.append(sub_folder) # -- Should already have been added...
            sub_folder_list = get_all_subfolders(jazz_client, sub_folder, path)
            result_list.extend(sub_folder_list)
    else:
        result_list.append(folder)

    log.logger.debug(f"{folder} Found {len(result_list)} folders: {result_list}")
    return result_list


def find_requirements(jazz_client, paths):
    folders = []
    artifacts = []
    for path in paths:
        log.logger.info(f"Reading {path}")
        folder = traverse_path(jazz_client, path)
        found_folders = get_all_subfolders(jazz_client, folder)
        for this_folder in found_folders:
            found_artifacts = this_folder.get_folder_artifacts()
            log.logger.info(f"Found {len(found_artifacts)} artifacts")
            folders.extend(found_artifacts)
            log.logger.info(f"Getting artifacts from uris...")
            subgroup = jazz_client.get_object_from_uri(found_artifacts)
            log.logger.info(f"got {len(subgroup)} items...")
            if len(subgroup) != len(found_artifacts):
                log.logger.error(f"Did not read correct number of resources. :-(")
            artifacts.extend(subgroup)

    log.logger.info(f"Found a total of {len(folders)} Folders and {len(artifacts)} Artifacts...")
    return folders, artifacts


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
    catalog_folders, catalog_artifacts = find_requirements(jazz_client, environment['catalog_paths'])
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

