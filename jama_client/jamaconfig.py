
class JamaConfig:
    def __init__(self, config=None):
        if config is not None:
            self.base_url = config['host']
            self.username = config['username']
            self.password = config['password']
            self.auth = (self.username, self.password)
            self.rest_url = self.base_url + "/rest/latest/"
            if 'verify' in config:
                verified = "verified"
                # Make certificate file relative to config file...
                config_directory = "" if 'config_directory' not in config else config['config_directory']
                server['verify'] = config_directory + '/' + config['verify']
            else:
                verified = "unverified"
                # -- Following code is supposed to ignore a certificate error, but it doesn't. :-(
                import requests
                from requests.packages.urllib3.exceptions import InsecureRequestWarning
                requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        self.verify_ssl = False  # True
