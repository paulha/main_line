from jazz import *
import utility_funcs.logger_yaml as log
import urllib3

from jira_class import Jira, get_query
from os.path import expanduser, pathsep, dirname, realpath
import sys


urllib3.disable_warnings()
jazz = Jazz(server_alias="production", config_path=JAZZ_CONFIG_PATH, use_cache=True, op_name=None)

JIRA_CONFIG_PATH = f"{dirname(realpath(sys.argv[0]))}/config.yaml{pathsep}~/.jira/config.yaml"
jira = Jira('jira01', JIRA_CONFIG_PATH, log=log.logger)

log.logger.info(f"Opening the collection")
#result_list = Folder(jazz).get_folder_artifacts(path="Programs/Keystone Lake Refresh (KSL-R)",
#                                                name="Keystone Lake Refresh | Bare Metal | O-MR1")
result_list = Folder(jazz).get_folder_artifacts(path="Programs/Broxton-P IVI (BXT-P-IVI)",
                                                name="Broxton-P IVI | AaaG-ACRN | P")
for resource_collection in jazz.get_object_from_uri(result_list[0]):
    if isinstance(resource_collection, Collection):
        requirement_set = resource_collection.requirement_set()
        log.logger.info(f"The collection contains {len(requirement_set)} requirements, reading...")
        requirements_by_id = { requirement.get_identifier(): requirement for requirement in jazz.get_object_from_uri(requirement_set)}
        log.logger.info(f"got {len(requirements_by_id)} Requirements")
    else:
        log.logger.error(f"Object {resource_collection} is not a collection")
        exit(-1)

epic_name = jira.get_field_name('Epic Name')
items_by_id = {getattr(item.fields, epic_name): item
               for item in jira.do_query('project=OAM and summary~"Keystone Lake Refresh | Bare Metal | O-MR1"')}
pass






















