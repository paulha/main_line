import json
import time
import warnings
from queue import Queue, Empty
from threading import Thread

import requests
from requests import HTTPError

import utility_funcs.logger_yaml as log
from jama_client.jamaconfig import JamaConfig


class JamaClient:
    def __init__(self, config=None, threads=16):
        self.jama_config = JamaConfig(config)
        self.threads = threads
        self.id_map = {}
        self.delete_list = []
        self.auth = self.jama_config.auth
        self.verify = self.jama_config.verify_ssl
        self.seconds = 2
        self.item_fieldname_cache = {}

        self.pacifier = 0
        self.itemtypes_by_name = {t['typeKey']: t for t in self.get_all('itemtypes')}
        self.itemtypes_by_id = {self.itemtypes_by_name[item]['id']: self.itemtypes_by_name[item]
                                    for item in self.itemtypes_by_name}
        # -- support for get_real_field_name():
        self.fields_by_type = {}  # structure used to translate names
        for item in self.itemtypes_by_name:
            itm = self.get_itemtype_by_name(item)
            self.fields_by_type[itm['typeKey']] = {}
            for field in itm['fields']:
                self.fields_by_type[itm['typeKey']][field['label']] = field

        # -- support for get_real_field_value():
        self.value_cache = {}

    def get_real_field_name(self, jama_item, name_to_look_up):
        field_info = None
        item_type = self.itemtypes_by_id[jama_item['itemType']]
        if item_type['id'] not in self.item_fieldname_cache:
            self.item_fieldname_cache[item_type['id']] = {}

        field_cache = self.item_fieldname_cache[item_type['id']]
        if name_to_look_up not in field_cache:
            for field in item_type['fields']:
                if field['label'] == name_to_look_up:
                    field_cache[name_to_look_up] = field
                    break
        try:
            field_info = field_cache[name_to_look_up]
        except KeyError as ke:
            raise ke
        return field_info

    def _get_real_field_name(self, jama_item, name_to_look_up):
        return self.fields_by_type[self.itemtypes_by_id[jama_item['itemType']]['typeKey']][name_to_look_up]

    def get_real_field_value(self, jama_item, name_to_look_up):
        name = name_to_look_up
        field_info = None
        try:
            field_info = self._get_real_field_name(jama_item, name_to_look_up)
        except Exception as e:
            # -- Exception is presumed to mean that this is not an aliased name...
            pass

        if field_info is not None:
            name = field_info['name']

        # -- if this is not a lookup value, we shouldn't do this...
        if field_info is not None and 'pickList' in field_info:
            value = jama_item['fields'][name]
            if value not in self.value_cache:
                # -- lookup the value:
                v = self.get_all("picklistoptions/{}".format(value))[0]
                self.value_cache[v['id']] = v
            value = self.value_cache[value]['name']
        elif field_info is not None and \
                (field_info['fieldType'] == 'DOCUMENT_TYPE_ITEM_LOOKUP' or
                 field_info['fieldType'] == 'LOOKUP'):
            # value = "DOCUMENT_TYPE_ITEM_LOOKUP" -- Should this lookup get cached? PROBABLY
            if name in jama_item['fields']:
                value = jama_item['fields'][name]
                if value not in self.value_cache:
                    v = self.get_all("abstractitems/{}".format(value))[0]
                    self.value_cache[v['id']] = v
                value = self.value_cache[value]['documentKey']
            else:
                value = None
        else:
            value = jama_item['fields'][name] if name in jama_item['fields'] else None
        return value

    def get_itemtype_by_name(self, name):
        return self.itemtypes_by_name[name]

    def get_itemtype_by_id(self, id):
        return self.itemtypes_by_id[id]

    def extract_id(self, response):
        json_response = json.loads(response)
        location = json_response["meta"]["location"].split('/')[-1]
        return location

    def update_location(self, item):
        parent = item["location"]["parent"]
        if "item" not in parent:
            raise Exception("Parent must be item: {}".format(item))

        if parent["item"] not in self.id_map:
            return item

        new_parent = self.id_map[parent["item"]]
        item["location"]["parent"]["item"] = new_parent
        return item

    def remove_read_only(self, item, response):
        message = response.text
        if "You cannot set read-only fields. fields:" not in message:
            raise Exception("Error {} in item: {}".format(response.text, item))
        fields = message[message.index("fields: ") + 8:]
        fields = fields[:len(fields) - 3]
        fields = [field.strip() for field in fields.split(',')]
        for field in fields:
            if field in item:
                del item[field]
            if field in item["fields"]:
                del item["fields"][field]

    def get(self, url):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return requests.get(url, auth=self.auth, verify=self.verify)


    def get_item(self, item_id):
        url = self.jama_config.rest_url + "items/" + str(item_id)
        response = self.get(url=url)
        json_response = json.loads(response.text)
        if json_response["meta"]["status"] == "Not Found":
            log.logger.debug(json_response)
            log.logger.debug("Item not found with id " + str(item_id))
        else:
            json_response['data']['tags'] = self.get_tags(item_id)
            return [json_response["data"]]

    def get_location(self, item_id):
        url = self.jama_config.rest_url + "items/" + str(item_id) + "/location"
        response = self.get(url=url)
        json_response = json.loads(response.text)
        if json_response["meta"]["status"] == "Not Found":
            log.logger.debug(json_response)
            log.logger.debug("Item not found with id " + str(item_id))
        else:
            return [json_response["data"]]

    def get_tags(self, item_id) -> []:
        url = self.jama_config.rest_url + "items/" + str(item_id) + "/tags"
        response = self.get(url=url)
        json_response = json.loads(response.text)
        if json_response["meta"]["status"] == "Not Found":
            log.logger.debug(json_response)
            log.logger.debug("Item not found with id " + str(item_id))
        else:
            return [item['name'] for item in json_response["data"]]

    def get_all_items(self, project=None, item_type=None, item_type_name_abbreviation=None, documentKey=None, contains=None, sortBy=None):
        def _builder(request, parameter, value):
            sep = '&' if request.find('?') != -1 else '?'
            return request+sep+parameter+'=%s'%value if value is not None else request

        item_type = self.itemtypes_by_name[item_type_name_abbreviation] \
                                                if item_type_name_abbreviation is not None else item_type
        request = _builder("abstractitems", "project", project)
        request = _builder(request, "itemType", item_type \
                                                if isinstance(item_type, int)
                                                else item_type['id'] if item_type is not None else None)
        request = _builder(request, "documentKey", documentKey)
        request = _builder(request, "contains", contains)
        request = _builder(request, "sortBy", sortBy)
        log.logger.debug(request)
        return self.get_all(request)

    def get_children(self, item_id):
        return self.get_all("items/{}/children".format(item_id))

    def get_descendants(self, item_id, use_multithreading=True):
        if use_multithreading:
            return self._get_descendants_mt(item_id)
        else:
            return self._get_descendants(item_id)

    @staticmethod
    def can_have_children(descendant, aproximate=True):
        if aproximate:
            return True if descendant['itemType'] in [92] \
                        or 'childItemType' in descendant \
                        else False
        else:
            return True if 'childItemType' in descendant \
                        or 'type' in descendant and descendant['type'] == 'items' \
                        else False

    def _get_descendants(self, item_id):
        """Returns composite list of all descenants of the item passed in.

        NOTE:   that the returned list does not include the root object!
        Author: Paul Hanchett"""
        descendants = self.get_children(item_id)
        heirs = []
        for descendant in descendants:
            # -- todo: Need to optimize here to not try to get children of items that won't have any...
            if JamaClient.can_have_children(descendant):
                descendants = self._get_descendants(descendant['id'])
                # Decorate with tags, too!
                for item in descendants:
                    item['tags'] = self.jama_client.get_tags(item['id'])

                heirs += descendants
                pass
            # else:
            #     heirs += self.get_descendants(descendant['id'])
            #     if len(heirs) != 0:
            #         pass

        descendants += heirs
        return descendants

    def _get_descendants_mt(self, id):
        # use_yield = False

        class _GetChild(Thread):
            inprocess_requests = 0
            max_requests = 0

            def __init__(self, jama_client, work_queue, result_queue):
                Thread.__init__(self)
                self.jama_client = jama_client
                self.work_queue = work_queue
                self.result_queue = result_queue
                self.stopping = False

            def run(self):
                while not self.stopping:
                    # Get the work from the queue and expand the tuple
                    try:
                        item = self.work_queue.get(timeout=0.1)
                    except Empty as e:
                        continue

                    _GetChild.inprocess_requests += 1
                    _GetChild.max_requests = _GetChild.inprocess_requests \
                                                if _GetChild.inprocess_requests > _GetChild.max_requests \
                                                else _GetChild.max_requests
                    descendants = self.jama_client.get_children(item)

                    # Decorate with tags, too!
                    for descendant in descendants:
                        descendant['tags'] = self.jama_client.get_tags(descendant['id'])

                    self.result_queue.put((descendants))
                    self.work_queue.task_done()
                    _GetChild.inprocess_requests -= 1

            def stop(self):
                self.stopping = True

        result_list = []
        thread_list = []
        max_work_que = 0

        # Create a queue to communicate with the worker threads
        work_queue = Queue()
        result_queue = Queue()

        # Create worker threads
        for x in range(self.threads):
            worker = _GetChild(self, work_queue, result_queue)
            worker.start()
            thread_list.append(worker)

        # Put the tasks into the queue as a tuple
        work_queue.put((id))

        # Causes the main thread to wait for the queue to finish processing all the tasks
        # read results till they are all done...
        # -- it takes both empty() and unfinished_tasks to get this right!
        while not work_queue.empty() or work_queue.unfinished_tasks != 0 or \
                not result_queue.empty() or result_queue.unfinished_tasks != 0:
            max_work_que = work_queue.unfinished_tasks if work_queue.unfinished_tasks > max_work_que else max_work_que

            try:
                descendants = result_queue.get(timeout=0.1)
            except Empty as e:
                continue

            for descendant in descendants:
                if JamaClient.can_have_children(descendant):
                    work_queue.put((descendant['id']))
                #if use_yield:
                #    yield descendant
                #else:
                result_list.append(descendant)

            result_queue.task_done()

        work_queue.join()

        for th in thread_list:
            th.stop()

        log.logger.info("Max queue length is %d, max requests is %d", max_work_que, _GetChild.max_requests)

        #if use_yield:
        #    return
        #else:
        return result_list

    def get_item_for_documentkey(self, document_key):
        items = self.get_all("abstractitems?documentKey={}".format(document_key))
        if len(items) > 1:
            raise Exception("Multiple items with ID: {}".format(document_key))
        if len(items) < 1:
            raise Exception("No items found with ID: {}".format(document_key))
        return items[0]

    def get_all(self, resource):
        all_results = []
        results_remaining = True
        current_start_index = 0
        delim = '&' if '?' in resource else '?'
        while results_remaining:
            start_at = delim + "startAt={}".format(current_start_index)
            url = self.jama_config.rest_url + resource + start_at

            self.pacifier += 1
            if (self.pacifier%40)==0:
                # self.pacifier = 0
                log.logger.info("Working... %s", self.pacifier)

            log.logger.debug(url)
            response = self.get(url)
            json_response = json.loads(response.text)
            log.logger.debug(json_response)
            if "pageInfo" not in json_response["meta"]:
                log.logger.debug(json_response)
                if 'data' not in json_response:
                    raise HTTPError("Malformed result!")
                return [json_response["data"]]
            result_count = json_response["meta"]["pageInfo"]["resultCount"]
            total_results = json_response["meta"]["pageInfo"]["totalResults"]
            results_remaining = current_start_index + result_count != total_results
            current_start_index += 20
            all_results.extend(json_response["data"])

        return all_results

    def get_picklist_options(self, id):
        return self.get_all("picklists/{}/options".format(id))

    def put(self, item):
        self.delay()
        if "isFootnote" in item:
            item["itemType"] = self.jama_config.text_type_id
            self.post_item(item)
            return item
        try:
            if "isFolder" not in item and "isText"not in item:
                self.put_item(item)
                return item
        except KeyError:
            if "itemType" in item and item["itemType"] == self.jama_config.text_type_id:
                item["isText"] = True
                item["isFolder"] = False
            elif "itemType" in item and item["itemType"] == self.jama_config.folder_type_id:
                item["isText"] = False
                item["isFolder"] = True
        try:
            # if both of these are set, folder should win
            if "isFolder" in item:
                item["childItemType"] = item["itemType"]
                item["itemType"] = self.jama_config.folder_type_id
            elif "isText" in item:
                item["itemType"] = self.jama_config.text_type_id

            self.replace_item(item)

        except KeyError:
            pass

    def put_item(self, item):
        self.delay()
        url = self.jama_config.rest_url + "items/{}?setGlobalIdManually=true".format(item["id"])
        # if "globalId" in item and self.gid not in item["globalId"]:
        #     url += "?setGlobalIdManually=true"
        item = self.update_location(item)

        try:
            response = requests.put(url, auth=self.auth, verify=self.verify, json=item)
            response.raise_for_status()
        except HTTPError as e:
            self.remove_read_only(item, e.response)
            self.put_item(item)

    def put_item_raw(self, item):
        self.delay()
        url = self.jama_config.rest_url + "items/{}?setGlobalIdManually=true".format(item["id"])
        try:
            response = requests.put(url, auth=self.auth, verify=self.verify, json=item)
            response.raise_for_status()
        except HTTPError as e:
            self.remove_read_only(item, e.response)
            self.put_item_raw(item)

    #
    #   -- I think this code is pretty shakey as it's based on my non-existent understanding
    #      of how JSON patches work. Don't trust it until you verify it!
    #
    def patch_item(self, item_to_patch, json_patch_request, set_globalid_manually=True):
        self.delay()
        url = self.jama_config.rest_url + "items/{}?setGlobalIdManually={}" \
                                          .format(item_to_patch["id"], set_globalid_manually)
        try:
            response = requests.patch(url, auth=self.auth, verify=self.verify, json=json_patch_request)
            response.raise_for_status()
        except HTTPError as e:
            self.remove_read_only(item_to_patch, e.response)
            self.post_item(item_to_patch)

    def post_item(self, item):
        self.delay()
        url = self.jama_config.rest_url + "items"
        try:
            response = requests.post(url, auth=self.auth, verify=self.verify, json=item)
            response.raise_for_status()
        except HTTPError as e:
            self.remove_read_only(item, e.response)
            self.post_item(item)

    def add_item_to_synceditems(self, item, synced_item):
        self.delay()
        url = self.jama_config.rest_url + "items/%d/synceditems" % synced_item['id']
        try:
            item_to_add = '{ "item": %d}' % item['id']
            # Even though we do want to post json, it didn't work until I did it myself... :-(
            response = requests.post(url, auth=self.auth, verify=self.verify,
                                     data=item_to_add, headers={'Content-Type': 'application/json',
                                                                'Accept': 'application/json'})
            response.raise_for_status()
        except HTTPError as e:
            self.remove_read_only(item, e.response)
            # -- Possible endless loop...
            self.add_item_to_synceditems(item, synced_item)

    def replace_item(self, item):
        self.delay()
        post_url = self.jama_config.rest_url + "items?project={}".format(item["project"])
        delete_id = item["id"]
        item = self.update_location(item)
        try:
            response = requests.post(post_url, auth=self.auth, verify=self.verify, json=item)
            response.raise_for_status()
            if "isFolder" in item:
                self.id_map[item["id"]] = self.extract_id(response.text)
            self.delete_list.append(delete_id)
        except HTTPError as e:
            self.remove_read_only(item, e.response)
            self.replace_item(item)
        return item

    def clean_up(self):
        delete_url = self.jama_config.rest_url + "items/{}"
        for url in [delete_url.format(url) for url in self.delete_list]:
            self.delay()
            requests.delete(url, auth=self.auth, verify=self.verify)

    def delay(self):
        time.sleep(self.seconds)



    def putAttachment(self):
        file = "itemtree.py"
        url = self.jama_config.rest_url + "attachments/2129057/" + file
        try:
            response = requests.put(url, auth=self.auth, verify=self.verify, json=json.load(file))
            response.raise_for_status()
        except HTTPError as e:
            log.logger.debug ("DOne")
