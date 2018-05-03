from main_line import *
from jazz_dng_client import JAZZ_CONFIG_PATH, Jazz
import pickle

from lxml import etree


def update_requirement_collection(jazz_server: str, config_path: str, folder_path: str, collection_name: str, requirement_list: list):
    """Presumes that collection already exists. Content of the collection will be *replaced*!"""
    from jazz_dng_client import Collection

    jazz_client = Jazz(jazz_server, config_path)
    catalog_folders, resource_collections = jazz_client.find_requirements(folder_path, name=collection_name)
    # OK, so we expect to find a single resource collection
    if len(resource_collections) == 1 and isinstance(resource_collections[0], Collection):
        collection = resource_collections[0]
        add_list = [item['URI'] for item in requirement_list]
        collection.get()
        collection.add_requirements(add_list)
        collection.put()

    else:
        # Something unexpected occured
        log.logger.error(f"Expected to find a single ResourceCollection but did not. Found {len(resource_collections)} instead.")

    return


def analyse(config, logg):
    environment = config['analyse']

    with open(environment['jira_pickle_file'], 'rb') as f:
        log.logger.info(f"Reading AREQ from '{environment['jira_pickle_file']}'")
        areq = pickle.load(f)
        log.logger.info(f"Reading PREQ from '{environment['jira_pickle_file']}'")
        preq = pickle.load(f)

    with open(environment['dng_pickle_file'], 'rb') as f:
        log.logger.info(f"Reading DNG ID's from '{environment['dng_pickle_file']}'")
        requirement_by_dngid = pickle.load(f)
        log.logger.info(f"Reading JAMA GID's from '{environment['dng_pickle_file']}'")
        requirement_by_gid = pickle.load(f)
        log.logger.info(f"Reading Jira KEY's from '{environment['dng_pickle_file']}'")
        requirement_by_jirakey = pickle.load(f)

    log.logger.info(f"Done reading")

    add_to_requirement_collection = []

    # Scan AREQ's
    missing_areqs = 0
    for item in areq:
        parent_key = item['PARENT']
        if parent_key not in requirement_by_jirakey:
            log.logger.error(f"DNG is missing Jira Feature {parent_key}, E-Feature: {item['KEY']} {item['SUMMARY']}")
            missing_areqs += 1
        else:
            add_to_requirement_collection.append(requirement_by_jirakey[parent_key])

    # Scan PREQ's
    missing_preqs = 0
    for item in preq:
        gid_key = item['GID']
        if gid_key not in requirement_by_gid:
            log.logger.error(f"DNG is missing JAMA GID {gid_key}, {item['KEY']} {item['SUMMARY']}")
            missing_preqs += 1
        else:
            add_to_requirement_collection.append(requirement_by_gid[gid_key])

    if missing_areqs or missing_preqs:
        log.logger.warning(f"DNG is missing AREQs: {missing_areqs}, missing PREQs: {missing_preqs}")

    # TODO: Update the ResourceCollection
    #       Shoud we read the existing collection and update with this list (what if something is removed)? But what if
    #       a requirement is added that *isn't* in the original project... It could disappear an no one would be the
    #       wiser.
    #
    #       OR the RequirementCollection could be (completely) regenerated each time.
    update_requirement_collection(environment['jazz_server'], JAZZ_CONFIG_PATH,
                                  [environment['requirement_collection_path']],
                                  environment['requirement_collection_name'],
                                  add_to_requirement_collection)

    return


if __name__ == "__main__":
    exit(mainline(analyse))

