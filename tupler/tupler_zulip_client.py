from collections import namedtuple
from enum import Enum
from html.parser import HTMLParser
from functools import wraps
import json

import requests
from requests.auth import HTTPBasicAuth


class Events(Enum):
    end_of_messages = 1


class MessageContentParser(HTMLParser):
    def __init__(self):
        super(MessageContentParser, self).__init__()
        self.buffer = ""

    def handle_data(self, data):
        self.buffer += data

    def collect(self):
        return self.buffer


class RequestError(Exception):

    def __init__(self, message):
        self.message = message


Message = namedtuple('Message', ['event_id', 'sender', 'recipient', 'subject',
                                 'content'])

Credentials = namedtuple('Credentials', ['server', 'email', 'api_key'])

endpoints = {'queue': 'register', 'subscriptions': 'users/me/subscriptions'}


def get_endpoint(credentials, endpoint_type):
    endpoint = None
    if endpoint_type in endpoints:
        endpoint = endpoints[endpoint_type]
    else:
        endpoint = endpoint_type
    return "{server}/api/v1/{endpoint}".format(server=credentials.server,
                                               endpoint=endpoint)


@wraps
def check_response(func):
    def response_check(*args, **kwargs):
        response = func(*args, **kwargs)
        if not response.ok:
            raise RequestError(response.text)
        return response
    return response_check


@check_response
def authenticated_get(credentials, endpoint, params=None):
    return requests.get(endpoint, auth=HTTPBasicAuth(
        credentials.email, credentials.api_key), params=params)


@check_response
def authenticated_post(credentials, endpoint, data):
    return requests.post(endpoint, auth=HTTPBasicAuth(
        credentials.email, credentials.api_key), data=data,
                         headers={"Content-Type":
                                  "application/x-www-form-urlencoded"})


def register_message_queue(credentials):
    queue_endpoint = get_endpoint(credentials, 'queue')
    register_response = authenticated_post(credentials, queue_endpoint,
                                           {"event_types": "[\"message\"]"})
    register_response_json = register_response.json()
    queue_id = register_response_json['queue_id']
    last_event_id = register_response_json['last_event_id']
    return (queue_id, last_event_id)


def get_events_from_queue(credentials, queue_id, last_event_id):
    events_endpoint = get_endpoint(credentials, 'events')
    endpoint = "{}?queue_id={}&last_event_id={}&dont_block=true".format(
        events_endpoint, queue_id, last_event_id)
    new_events = authenticated_get(credentials, endpoint)
    new_events_json = new_events.json()
    if new_events_json['result'] == 'error':
        queue_id, last_event_id = register_message_queue(credentials)
        return get_events_from_queue(credentials, queue_id, last_event_id)
    return new_events_json['events']


def get_message(message):
    if 'message' in message:
        message_data = message['message']
    else:
        message_data = message
    sender = message_data['sender_full_name']
    recipient = message_data['display_recipient']
    subject = message_data['subject']
    content = message_data['content']
    event_id = message['id']
    return Message(event_id, sender, recipient, subject, content)


def get_new_messages(credentials, queue_id, last_event_id):
    return get_events_from_queue(credentials, queue_id, last_event_id)


def get_old_messages(credentials, anchor=0, num_before=0, num_after=0,
                     use_first_unread_anchor=False):
    params = {'anchor': anchor, 'num_before': num_before,
              'num_after': num_after}
    if use_first_unread_anchor:
        params['use_first_unread_anchor'] = 'true'
        params['narrow'] = '[]'
    messages_endpoint = get_endpoint(credentials, 'messages')
    return authenticated_get(credentials, messages_endpoint,
                             params=params)


def parse_html_content(message):
    message_content = message['content']
    parser = MessageContentParser()
    parser.feed(message_content)
    parsed = parser.collect()
    del(parser)
    return parsed


def get_unread_messages(credentials, previous_messages=10,
                        following_messages=10):
    unread_messages_response = get_old_messages(
        credentials, anchor=0, num_before=previous_messages,
        num_after=following_messages, use_first_unread_anchor=True)
    unread_messages_json = unread_messages_response.json()
    unread_messages = unread_messages_json['messages']
    for unread_message in unread_messages:
        unread_message['content'] = parse_html_content(unread_message)
    return [get_message(m) for m in unread_messages]


def get_subscriptions(credentials):
    subscriptions_endpoint = get_endpoint(credentials, 'subscriptions')
    subscriptions_response = authenticated_get(
        credentials, subscriptions_endpoint)
    subscriptions_response_json = subscriptions_response.json()
    return [s['name'] for s in subscriptions_response_json['subscriptions']]


def _get_subscription_body(stream_names):
    return json.dumps([{"name": s} for s in stream_names])


def subscribe_to_streams(credentials, stream_names):
    subscriptions_endpoint = get_endpoint(credentials, 'subscriptions')
    subscription_list = None
    if not isinstance(stream_names, list):
        subscription_list = [stream_names]
    else:
        subscription_list = stream_names
    subscription_body = "subscriptions={}".format(_get_subscription_body(
        subscription_list))
    return authenticated_post(credentials, subscriptions_endpoint,
                              subscription_body)


def send_stream_message(credentials, stream, subject, content):
    messages_endpoint = get_endpoint(credentials, 'messages')
    message_payload = "type=stream&to={}&subject={}&content={}".format(
        stream, subject, content)
    return authenticated_post(credentials, messages_endpoint, message_payload)


def send_private_message(credentials, recipient, content):
    messages_endpoint = get_endpoint(credentials, 'messages')
    message_payload = "type=private&to={}&content={}".format(
        recipient, content)
    return authenticated_post(credentials, messages_endpoint, message_payload)


def message_loop(credentials):
    queue_id, last_event_id = register_message_queue(credentials)
    while True:
        new_messages = get_new_messages(credentials, queue_id, last_event_id)
        for message in new_messages:
            message_tuple = get_message(message)
            last_event_id = message_tuple.event_id
            yield message_tuple
        else:
            yield Events.end_of_messages


def get_credentials(server, email, api_key):
    credentials = Credentials(server=server, email=email, api_key=api_key)
    return credentials
