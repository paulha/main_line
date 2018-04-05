from jazz import *
import utility_funcs.logger_yaml as log
import urllib3

from jira_class import Jira, get_query
from os.path import expanduser, pathsep, dirname, realpath
import sys

JIRA_CONFIG_PATH = f"{dirname(realpath(sys.argv[0]))}/config.yaml{pathsep}~/.jira/config.yaml"

config = {
    'test': {
        'jazz server': 'production',
        'path': "Programs/Broxton-P IVI (BXT-P-IVI)",
        'name': "Broxton-P IVI | AaaG-ACRN | P",
        'jira server': 'jira01',
        'jira query': 'project=OAM and summary~"Keystone Lake Refresh | Bare Metal | O-MR1"',
     },

    'production': {
        'jazz server': 'production',
        'path': "Programs/Keystone Lake Refresh (KSL-R)",
        'name': "Keystone Lake Refresh | Bare Metal | O-MR1",
        'jira server': 'jira01',
        'jira query': 'project=OAM and summary~"Keystone Lake Refresh | Bare Metal | O-MR1"',
    }
}
environment = config['test']

def read_jazz_requirements(jazz_client, path: str, name: str) -> dict:
    requirements_by_id = {}
    log.logger.info(f"Opening the collection {name}")
    result_list = Folder(jazz_client).get_folder_artifacts(path=path, name=name)
    for resource_collection in jazz.get_object_from_uri(result_list[0]):
        if isinstance(resource_collection, Collection):
            requirement_set = resource_collection.requirement_set()
            log.logger.info(f"The collection contains {len(requirement_set)} requirements, reading...")
            requirements_by_id = { requirement.get_identifier(): requirement for requirement in jazz.get_object_from_uri(requirement_set)}
            log.logger.info(f"got {len(requirements_by_id)} Requirements")
        else:
            log.logger.error(f"Object {resource_collection} is not a collection")
            exit(-1)
    return requirements_by_id

def read_jazz(jazz_client):
    return read_jazz_requirements(jazz_client=jazz_client,
                                  path=environment['path'],
                                  name=environment['name'])


def read_jira_epics(jira_client, query):
    epic_name = jira_client.get_field_name('Epic Name')
    items_by_id = {getattr(item.fields, epic_name): item
                   for item in jira_client.do_query(environment['jira query'])}
    return items_by_id

def read_jira():
    return read_jira_epics(query=environment['jira query'])


urllib3.disable_warnings()
jazz = Jazz(server_alias=environment['jazz server'], config_path=JAZZ_CONFIG_PATH, use_cache=True, op_name=None)
jira = Jira(environment['jira server'], JIRA_CONFIG_PATH, log=log.logger)
epic_name = jira.get_field_name('Epic Name')
requirements_by_id = read_jazz(jazz_client=jazz)
items_by_id = read_jira(jira_client=jira)

missing_requirements = [requirement for requirement in requirements_by_id
                        if requirement.get_identifier() not in items_by_id]
missing_items = [item for item in items_by_id
                 if getattr(item.fields, epic_name) not in requirements_by_id]




















