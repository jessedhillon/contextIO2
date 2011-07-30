import json
import re
from urllib import urlencode, quote
from oauth2 import Request, Consumer, Client, SignatureMethod_HMAC_SHA1 as sha1

from util import as_bool, as_datetime, process_person_info, uncamelize

class ContextIO(object):
    url_base = "https://api-preview.context.io"

    def __init__(self, consumer_key, consumer_secret):
        self.consumer = Consumer(key=consumer_key, secret=consumer_secret)
        self.client = Client(self.consumer)
        self.client.set_signature_method(sha1())
        self.base_uri = '2.0'

    def request_uri(self, uri, method="GET", params={}, headers={}):
        url = '/'.join((self.url_base, self.base_uri, uri))
        response, body = self.request(url, method, params, headers)
        status = int(response['status'])

        if status == 200:
            body = json.loads(body)
            return body

        else:
            self.handle_request_error(response, body)

    def request(self, url, method, params, headers):
        if params:
            url += '?' + urlencode(params)

        print "{method} {url}".format(url=url, method=method)
        return self.client.request(url, method, headers=headers)

    def get_accounts(self):
        return [Account(self, obj) for obj in self.request_uri('accounts')]

    def post_account(self, email, first_name=None, last_name=None):
        pass

    def delete_account(self, account_id):
        pass

    def put_account(self, first_name=None, last_name=None):
        pass

    def handle_request_error(self, response, body):
        import pdb; pdb.set_trace()
        messages = []
        try:
            body = json.loads(body)
            for message in body['messages']:
                if message['type'] == 'error':
                    messages.append("error {0}".format(message['code']))
            raise Exception('HTTP {status}: {message}'.format(status=response['status'], message=', '.join(messages)))

        except ValueError:
            raise Exception('HTTP {status}: {body}'.format(status=response['status'], body=body))

class Resource(object):
    def __init__(self, parent, base_uri, defn):
        defn = uncamelize(defn)

        for k in self.__class__.keys:
            if k in defn:
                setattr(self, k, defn[k])
            else:
                setattr(self, k, None)

        self.parent = parent
        self.base_uri = quote(base_uri.format(**defn))

    def uri_for(self, *elems):
        return self.base_uri + '/' + ('/'.join(elems))

    def request_uri(self, uri_elems, method="GET", params={}):
        uri = self.uri_for(uri_elems)
        return self.parent.request_uri(uri, method=method, params=params)
        
    @staticmethod
    def sanitize_params(params, clean_keys):
        return dict((k, params[k]) for k in clean_keys if k in params)

class Account(Resource):
    keys = ['username', 'first_name', 'last_name', 'created', 'password_expired', 'sources', 'suspended', 'id', 'email_addresses']

    def __init__(self, parent, defn):
        super(Account, self).__init__(parent, 'accounts/{id}', defn)

        self.suspended = as_bool(self.suspended)
        self.password_expired = as_bool(self.password_expired)

    def get_contacts(self, **params):
        params = Resource.sanitize_params(params, ['search', 'active_before', 'active_after', 'limit', 'offset'])
        return [Contact(self, obj) for obj in self.request_uri('contacts', params=params).get('matches')]

    def get_email_addresses(self):
        return self.request_uri('email_addresses')

    def get_files(self, **params):
        params = Resource.sanitize_params(params, ['name', 'email', 'to', 'from', 'cc', 'bcc', 'date_before', 'date_after', 'indexed_before', 'indexed_after', 'group_by_revisions', 'limit', 'offset'])
        return [File(self, obj) for obj in self.request_uri('files', params=params)]

    def get_messages(self, **params):
        params = Resource.sanitize_params(params, ['subject', 'email', 'to', 'from', 'cc', 'bcc', 'date_before', 'date_after', 'indexed_before', 'indexed_after', 'include_body', 'include_headers', 'body_type', 'limit', 'offset'])
        for key in ['include_headers', 'include_body']:
            if key in params:
                params[key] = '1' if params[key] is True else '0' 

        return [Message(self, obj) for obj in self.request_uri('messages', params=params)]

    def get_sources(self):
        return self.request_uri('sources')

    def post_sync(self):
        pass

    def get_webhooks(self):
        return self.request_uri('webhooks')

class Contact(Resource):
    keys = ['count', 'thumbnail', 'email', 'name']

    def __init__(self, parent, defn):
        super(Contact, self).__init__(parent, 'contacts/{email}',  defn)

    def get_files(self, **params):
        params = Resource.sanitize_params(params, ['limit', 'offset'])
        body = self.request_uri('files', params=params)

        result = []
        for obj in body:
            file_name = obj.get('file_name')
            occurrences = []
            for o in obj.get('occurrences'):
                occurrences.append({
                    'file': File(self.parent, o),
                    'message': Message(self.parent, o)
                })

            result.append({
                'file_name': obj.get('file_name'),
                'latest_date': as_datetime(obj.get('latestDate')),
                'occurrences': occurrences
            })

        return result

    def get_messages(self, **params):
        params = Resource.sanitize_params(params, ['limit', 'offset'])
        return self.request_uri('messages', params=params)

    def get_threads(self, **params):
        params = Resource.sanitize_params(params, ['limit', 'offset'])
        return self.request_uri('threads', params=params)

class File(Resource):
    keys = ['person_info', 'occurrences', 'body_section', 'addresses', 'file_name', 'email_message_id', 'supports_preview', 'gmail_thread_id', 'file_id', 'gmail_message_id', 'date', 'file_name_structure', 'size', 'type', 'message_id', 'subject']

    def __init__(self, parent, defn):
        super(File, self).__init__(parent, 'files/{file_id}', defn)

        if 'person_info' in defn:
            person_info, to, frm = process_person_info(parent, defn['person_info'], defn['addresses'])

            self.person_info = person_info
            self.addresses = {
                'to': to,
                'from': frm
            }
            self.date = as_datetime(self.date)

    def get_changes(self, file_id=None):
        if file_id:
            if isinstance(file_id, File):
                file_id = file_id.file_id
            return self.request_uri('changes/' + file_id)

        else:
            return self.request_uri('changes')

    def get_content(self):
        return self.request_uri('content')

    def get_related(self):
        return self.request_uri('related')

    def get_revisions(self):
        return self.request_uri('revisions')

class Message(Resource):
    keys = ['body', 'headers', 'date', 'subject', 'addresses', 'files', 'message_id', 'email_message_id', 'gmail_message_id', 'gmail_thread_id', 'person_info']
    body = None
    flags = None
    headers = None
    thread = None

    def __init__(self, parent, defn):
        super(Message, self).__init__(parent, 'messages/{message_id}', defn)

        person_info, to, frm = process_person_info(parent, defn['person_info'], defn['addresses'])
        self.person_info = person_info
        self.addresses = {
            'to': to,
            'from': frm
        }
        self.date = as_datetime(self.date)

        if 'files' in defn:
            self.files = [File(self.parent, f) for f in defn['files']]

        if 'headers' in defn:
            self.process_headers(defn['headers'])

    def process_headers(self, response):
        hlist = []
        for line in response.strip().splitlines():
            if re.search('^\s', line):
                hlist[-1][1] += ' ' + line.strip()
            else:
                key, value = line.split(':', 1)
                hlist.append([key, value.strip()])

        self.headers = {}
        for h in hlist:
            key, value = h

            if key not in self.headers:
                self.headers[key] = value
            else:
                if isinstance(self.headers[key], list):
                    self.headers[key].append(value)
                else:
                    v = self.headers[key]
                    self.headers[key] = [v] + [value]


    def get_body(self):
        if self.body is None:
            self.body = self.request_uri('body')
        return self.body

    def get_flags(self):
        if self.flags is None:
            self.flags = self.request_uri('flags')
        return self.flags

    def get_headers(self):
        if self.headers is None:
            response = self.request_uri('headers')
            self.process_headers(response)
        return self.headers

    def get_thread(self):
        if self.thread is None:
            self.thread = self.request_uri('thread')
        return self.thread
