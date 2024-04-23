# New module for broadcasting messages

import requests

# Get the list of broadcast users based on the location table


def broadcast_message(message, endpoints):
    responses = []
    for endpoint in endpoints:
        try:
            response = requests.post(endpoint, json={'message': message})
            responses.append((endpoint, response.status_code))
        except requests.exceptions.RequestException as e:
            responses.append((endpoint, str(e)))
    return responses
