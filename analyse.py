from main_line import *
import urllib3
import sys
import regex as re

from jazz_dng_client import *
from jira_class import Jira
from lxml import etree
import pickle


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
        if item['PARENT'] not in requirement_by_jirakey:
            log.logger.error(f"DNG is missing Jira Feature {item['PARENT']}, E-Feature: {item['KEY']} {item['SUMMARY']}")
            missing_areqs += 1
        else:
            add_to_requirement_collection.append(item)

    # Scan PREQ's
    missing_preqs = 0
    for item in preq:
        if item['GID'] not in requirement_by_gid:
            log.logger.error(f"DNG is missing JAMA GID {item['GID']}, {item['KEY']} {item['SUMMARY']}")
            missing_preqs += 1
        else:
            add_to_requirement_collection.append(item)

    if missing_areqs or missing_preqs:
        log.logger.warning(f"DNG is missing AREQs: {missing_areqs}, missing PREQs: {missing_preqs}")

    return


if __name__ == "__main__":
    exit(mainline(analyse))

