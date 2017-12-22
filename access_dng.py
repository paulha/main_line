import requests

# -- Support
import sys
from os.path import pathsep, dirname, realpath
from utility_funcs.search import get_server_info
import utility_funcs.logger_yaml as log

from lxml import etree

# -- Set up logger...
LOG_CONFIG_FILE = 'logging.yaml'+pathsep+dirname(realpath(sys.argv[0]))+'/logging.yaml'
log.setup_logging("logging.yaml", override={'handlers': {'info_file_handler': {'filename': 'audit_jama_jira_matchup.log'}}})
log.logger.setLevel(log.logging.getLevelName("INFO"))
log.logger.disabled = False

JAZZ_CONFIG_FILE = dirname(realpath(sys.argv[0])) + '/config.yaml' + pathsep + '~/.jazz/config.yaml'

#----------------------------------------------------
#       Fill in valid username and password!
#----------------------------------------------------
try:
    jazz_config = get_server_info("dng", JAZZ_CONFIG_FILE)  # possible FileNotFoundError
except FileNotFoundError as f:
    self.log.fatal("Can't open JAZZ authentication configuration file: %s" % f)
    raise FileNotFoundError("Can't find Jazz configuration file", JAZZ_CONFIG_FILE)

log.logger.info(f"Using JAMA server instance {jazz_config['host']}{jazz_config['instance']}")


"""
if False:
    # -- OTC values
    authenticate = 'https://rtc.intel.com/rrc/auth/j_security_check'
    get_root_services = 'https://rtc.intel.com/rrc/rootservices'
    get_catalog = 'https://rtc.intel.com/rrc/oslc_rm/catalog'
else:
    # -- RongxunX's values
    authenticate = 'https://rtc.intel.com/jts/j_security_check'
    get_root_services = 'https://rtc.intel.com/dng0001001/rootservices'
    get_catalog = 'https://rtc.intel.com/dng0001001/oslc_rm/catalog'
    # _zQHY0a_4EeekDP1y4xXYPQ is the project ID of "SSG-OTC Product Management - DNG"
    get_project_services = 'https://rtc.intel.com/dng0001001/oslc_rm/_zQHY0a_4EeekDP1y4xXYPQ/services.xml'
"""

with requests.Session() as sess:
    # -- Using a session seems to work better than isolated gets and puts.
    #    Pretty sure this is working becasue if I intentionally make the login name invalid
    #    both the login_response and catalog_response indicate failure.
    #
    #    During the course of this login we get redirected to "https://rtc.intel.com/rrc/auth"
    #    which results in an error message: 'Invalid path to authentication servlet.' None the
    #    less, the login apparently succeeds.
    #
    login_response = sess.post(f"{jazz_config['host']}{jazz_config['instance']}/auth/j_security_check",
                               headers={"Content-Type": "application/x-www-form-urlencoded"},
                               data=f"j_username={jazz_config['username']}&j_password={jazz_config['password']}",
                               verify=False)
    print(f"Login response: {login_response.status_code}")
    print(f"Login cookies: {login_response.cookies}")
    # print(f"{login_response.text}\n=========================")

    # -- This line works, even if login above fails...
    root_services_response = sess.get(f"{jazz_config['host']}{jazz_config['instance']}/rootservices",
                                      headers={'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml'},
                                      stream=True, verify=False)
    print(f"Root Services response: {root_services_response.status_code}")
    print(f"Root Services cookies: {root_services_response.cookies}")
    # Note: Printing this here, causes the parse below to fail (because the stream is already read...?)
    # print(f"{root_services_response.text}\n=========================")

    # -- This line only gives a result if the login succeeded, but the output is MUCH shorter than I expect.
    olsc_namespaces = {
        'dc': 'http://purl.org/dc/terms/',
        # 'jfs_proc' : 'http://jazz.net/xmlns/prod/jazz/process/1.0/',
        # 'oslc_disc': 'http://open-services.net/xmlns/discovery/1.0/',
        'oslc_rm': "http://open-services.net/xmlns/rm/1.0/",
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'oslc': 'http://open-services.net/ns/core#',
        'dcterms': "http://purl.org/dc/terms/",
        'jp': "http://jazz.net/xmlns/prod/jazz/process/1.0/"
    }
    root_services_response.raw.decode_content = True
    pa_root_services = etree.parse(root_services_response.raw)
    catalog_url = pa_root_services.xpath('//oslc_rm:rmServiceProviders/@rdf:resource', namespaces=olsc_namespaces)
    log.logger.info(f"Catalog URL is {catalog_url}")

    catalog_response = sess.get(catalog_url[0],
                                headers={'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml'},
                                stream=True, verify=False)
    print(f"Catalog response: {catalog_response.status_code}")
    print(f"Catalog cookies: {catalog_response.cookies}")

    catalog_response.raw.decode_content = True
    pa_project_services = etree.parse(catalog_response.raw)
    log.logger.info(f"{etree.tostring(pa_project_services, pretty_print=True)}\n=========================")
    projects = pa_project_services.xpath('//oslc:ServiceProvider', namespaces=olsc_namespaces)
    log.logger.info(f"Projects is {projects}")

    catalog_services = [
        {
            'services': project.xpath('//oslc:ServiceProvider/@rdf:about', namespaces=olsc_namespaces)[0],
            'title': project.xpath('dcterms:title/text()', namespaces=olsc_namespaces)[0],
            'registry': project.xpath('jp:consumerRegistry/@rdf:resource', namespaces=olsc_namespaces)[0],
            'details': project.xpath('oslc:details//@rdf:resource', namespaces=olsc_namespaces)[0],
        }
        for project in projects
    ]
    log.logger.info(f"{catalog_services}")

    # -- This line gets services of project "SSG-OTC Product Management - DNG"

    project_services_response = sess.get(catalog_services[1]['services'],
                                         headers={'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml'},
                                         stream=True, verify=False)
    print(f"Project Services response: {project_services_response.status_code}")
    print(f"Project Services cookies: {project_services_response.cookies}")
    # print(f"{project_services_response.text}\n=========================")

    project_services_response.raw.decode_content = True
    pa_services = etree.parse(project_services_response.raw)
    log.logger.info(f"{etree.tostring(pa_services, pretty_print=True)}\n=========================")
    services = pa_services.xpath('//oslc:service', namespaces=olsc_namespaces)
    log.logger.info(f"Projects is {projects}")

    services = [
        {
            #'services': project.xpath('//oslc:ServiceProvider/@rdf:about', namespaces=olsc_namespaces)[0],
            'title': service.xpath('./oslc:Service//dcterms:title/text()', namespaces=olsc_namespaces),
            #'registry': project.xpath('jp:consumerRegistry/@rdf:resource', namespaces=olsc_namespaces)[0],
            #'details': project.xpath('oslc:details//@rdf:resource', namespaces=olsc_namespaces)[0],
        }
        for service in services
    ]
    log.logger.info(f"{services}")

