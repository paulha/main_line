import yaml
import urllib3
from os.path import expanduser, pathsep, dirname, realpath
import sys

import utility_funcs.logger_yaml as log


JIRA_CONFIG_PATH = f"{dirname(realpath(sys.argv[0]))}/jira.yaml{pathsep}~/.jira/config.yaml"
JAMA_CONFIG_PATH = f"{dirname(realpath(sys.argv[0]))}/jama.yaml{pathsep}~/.jama/config.yaml"
JAZZ_CONFIG_PATH = f"{dirname(realpath(sys.argv[0]))}/jazz.yaml{pathsep}~/.jazz/config.yaml"


def mainline(action):
    try:
        with open("environments.yaml", "r") as f:
            config = yaml.load(f)
    except FileNotFoundError as nf:
        log.logger.error("File 'environments.yaml' not found %s", nf)
        exit(-1)

    action(config, log)
    log.logger.info("Done.")


