import requests

#----------------------------------------------------
#       Fill in valid username and password!
#----------------------------------------------------
username = 'pfhanchx'
password = 'Platinum2017.4'

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

with requests.Session() as sess:
    # -- Using a session seems to work better than isolated gets and puts.
    #    Pretty sure this is working becasue if I intentionally make the login name invalid
    #    both the login_response and catalog_response indicate failure.
    #
    #    During the course of this login we get redirected to "https://rtc.intel.com/rrc/auth"
    #    which results in an error message: 'Invalid path to authentication servlet.' None the
    #    less, the login apparently succeeds.
    #
    login_response = sess.post(authenticate,
                               headers={"Content-Type": "application/x-www-form-urlencoded"},
                               data=f"j_username={username}&j_password={password}",
                               verify=False)
    print(f"Login response: {login_response.status_code}")
    print(f"Login cookies: {login_response.cookies}")
    print(f"{login_response.text}\n=========================")

    # -- This line works, even if login above fails...
    root_services_response = sess.get(get_root_services,
                                      headers={'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml'})
    print(f"Root Services response: {root_services_response.status_code}")
    print(f"Root Services cookies: {root_services_response.cookies}")
    print(f"{root_services_response.text}\n=========================")

    # -- This line only gives a result if the login succeeded, but the output is MUCH shorter than I expect.
    catalog_response = sess.get(get_catalog,
                                headers={'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml'})
    print(f"Catalog response: {catalog_response.status_code}")
    print(f"Catalog cookies: {catalog_response.cookies}")
    print(f"{catalog_response.text}\n=========================")

    # -- This line gets services of project "SSG-OTC Product Management - DNG"
    project_services_response = sess.get(get_project_services,
                                         headers={'OSLC-Core-Version': '2.0', 'Accept': 'application/rdf+xml'})
    print(f"Project Services response: {project_services_response.status_code}")
    print(f"Project Services cookies: {project_services_response.cookies}")
    print(f"{project_services_response.text}\n=========================")

