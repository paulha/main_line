from main_line import *
import urllib3
import sys
import regex as re

from jazz_dng_client import *
from lxml import etree


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

def get_catalog(config, log):
    environment = config['DNG_Catalog']
    jazz_client = Jazz(environment['jazz_server'], JAZZ_CONFIG_PATH)
    catalog_folders, catalog_artifacts = find_requirements(jazz_client, environment['catalog_paths'])
    lookup = {x.get_identifier(): x for x in catalog_artifacts}
    requirement = lookup['50161']
    ext_id = requirement.external_system_id()
    requirement_by_dngid = {}
    requirement_by_jirakey = {}
    requirement_by_gid = {}
    jira_key_regex = r"^[A-Za-z]+-\d+"
    is_jira_key = re.compile(jira_key_regex)
    gid_regex = r"^\d+-\d+"
    is_gid = re.compile(gid_regex)
    for requirement in catalog_artifacts:
        dngid = requirement.get_identifier()
        key = str(requirement.external_system_id()).strip()

        requirement_by_dngid[dngid] = requirement
        if re.search(jira_key_regex, key): # is_jira_key.match(key):
            if key in requirement_by_jirakey:
                log.logger.warning(f"Requirement {dngid} and Requirement {requirement_by_jirakey[key].get_identifier()} duplicated jira key {key}")
            else:
                requirement_by_jirakey[key] = requirement

        elif re.search(gid_regex, key): #   is_gid.match(key):
            if key in requirement_by_gid:
                log.logger.warning(f"Requirement {dngid} and Requirement {requirement_by_gid[key].get_identifier()} duplicated GID key {key}")
            else:
                requirement_by_gid[key] = requirement

    pass


if __name__ == "__main__":
    exit(mainline(get_catalog))

