from collections import namedtuple
import requests
from requests.auth import HTTPBasicAuth
from time import sleep

Message = namedtuple('Message', ['event_id', 'sender', 'recipient', 'subject',
                                 'content'])

Credentials = namedtuple('Credentials', ['server', 'email', 'api_key'])


def get_endpoint(credentials, endpoint_type):
    endpoint = None
    if endpoint_type == 'queue':
        endpoint = 'register'
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
    formatted_message = "{sender}:{stream_and_topic}\n{content}".format(
        sender=message_data['sender_full_name'],
        stream_and_topic=stream_and_topic,
        topic=message_data['subject'],
        content=message_data['content']
    )
    message_id = message['id']
    return (message_id, formatted_message)


def get_new_messages(credentials, queue_id, last_event_id):
    return get_events_from_queue(credentials, queue_id, last_event_id)


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
            sleep(1)
