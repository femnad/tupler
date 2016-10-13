from collections import namedtuple
from enum import Enum
import json
import requests
from requests.auth import HTTPBasicAuth


class Events(Enum):
    end_of_messages = 1

Message = namedtuple('Message', ['event_id', 'sender', 'recipient', 'subject',
                                 'content'])

Credentials = namedtuple('Credentials', ['server', 'email', 'api_key'])


def get_endpoint(credentials, endpoint_type):
    endpoint = None
    if endpoint_type == 'queue':
        endpoint = 'register'
    elif endpoint_type == 'subscriptions':
        endpoint = 'users/me/subscriptions'
    else:
        endpoint = endpoint_type
    return "{server}/api/v1/{endpoint}".format(server=credentials.server,
                                               endpoint=endpoint)


def authenticated_get(credentials, endpoint):
    return requests.get(endpoint, auth=HTTPBasicAuth(
            credentials.email, credentials.api_key))


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


def format_message(message):
    if type(message) == str:
        return message
    message_data = message['message']
    recipient = message_data['display_recipient']
    stream_and_topic = "" if isinstance(recipient, list) \
        else "\n{} > {}\n".format(
                message_data['display_recipient'],
                message_data['subject'])
    formatted_message = "{sender}:{stream_and_topic}{content}".format(
        sender=message_data['sender_full_name'],
        stream_and_topic=stream_and_topic,
        topic=message_data['subject'],
        content=message_data['content']
    )
    message_id = message['id']
    return (message_id, formatted_message)


def get_new_messages(credentials, queue_id, last_event_id):
    return get_events_from_queue(credentials, queue_id, last_event_id)


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
            message_id, formatted_message = format_message(message)
            last_event_id = message_id
            yield formatted_message
        else:
            yield Events.end_of_messages
