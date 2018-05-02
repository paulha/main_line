from main_line import *
import urllib3
import sys
import regex as re

from jazz_dng_client import *
from jira_class import Jira
from lxml import etree
import pickle
import re


def tos( element ):
    return etree.tostring(element, xml_declaration=True)


def read_jira_partial(jira_client, query):
    items = [item for item in jira_client.do_query(query)]
    return items

def get_platform(config, logg):
    environment = config['Platform_Content']
    jira_client = Jira(environment['jira_server'], JIRA_CONFIG_PATH, log=logg.logger)
    gid = jira_client.get_field_name('Global ID')
    assignee = jira_client.get_field_name('Assignee')
    validation = jira_client.get_field_name('Verification')
    description = jira_client.get_field_name('Description')

    def get_jira_item(item):
        return {
            'KEY': str(item.key),
            # Remove version and platform inside square brackets...
            'SUMMARY': re.sub(r'^\[.*]\[.*]\s*(\[AaaG])*', "", getattr(item.fields, 'summary', '')),
            'DESCRIPTION': getattr(item.fields, description),
            'GID': str(getattr(item.fields, gid)) if getattr(item.fields, gid, None) is not None else None,
            'PARENT': str(item.fields.parent.key) if getattr(item.fields, 'parent', None) is not None else None,
            'ASSIGNEE': str(getattr(item.fields, assignee)),
            'VALIDATION': str(getattr(item.fields, validation)),
        }

    log.logger.info(f"Reading AREQ with '{environment['areq']}'")
    areq = read_jira_partial(jira_client, environment['areq'])
    # -- todo: Remember lead and validation!
    areq_features = [get_jira_item(item) for item in areq]
    log.logger.info(f"read {len(areq)} AREQ items")
    log.logger.info(f"Reading PREQ with '{environment['preq']}'")
    preq = read_jira_partial(jira_client, environment['preq'])
    # -- todo: Remember lead and validation!
    log.logger.info(f"read {len(preq)} PREQ items")
    preq_gids = [get_jira_item(item) for item in preq]

    with open(environment['pickle_file'], 'wb') as f:
        log.logger.info(f"Writing AREQ to picklefile '{environment['pickle_file']}'")
        pickle.dump(areq_features, f)
        log.logger.info(f"Writing PREQ to picklefile '{environment['pickle_file']}'")
        pickle.dump(preq_gids, f)

    return


if __name__ == "__main__":
    exit(mainline(get_platform))

