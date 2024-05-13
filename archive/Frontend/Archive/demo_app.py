# Exposing Zentica application
from quart import Quart, render_template_string, websocket, request
from quart_cors import cors
import socketio


#Real time communication
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCIceCandidate, RTCDataChannel

# Application specific
from db import get_device_collection, get_location_collection, get_active_user_endpoints
from broadcast import broadcast_message

#Generic Packages
from datetime import datetime
from bson.json_util import dumps
import json

# Create Quart app instance
app = Quart(__name__)
app.config['DEBUG'] = True
app = cors(app)
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*', )
socketio_app_demo = socketio.ASGIApp(sio, app)
# socketio_app_demo = socketio.ASGIApp(MySocketServer().sio, app)


# import socketio

# class MySocketServer:
#     def __init__(self):
#         self.sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
#         self.sio.on('connect', self.connect)
#         self.sio.on('disconnect', self.disconnect)
#         self.sio.on('message', self.message)
#         self.shared_var = {}

#     def connect(self, sid, environ):
#         print("connect ", sid, self.shared_var)

#     def disconnect(self, sid):
#         print("disconnect ", sid, self.shared_var)

#     def message(self, sid, data):
#         message = json.loads(data)
#         msg_type = message['type']
#         if msg_type == 'offer':
#             shared_var = {"sid": sid, "state": "broadcast"}
#     #         handle_offer() # Broadcast the offer to rest of the connected clients except sender(Use SID from the event)
#             await sio.send(data, skip_sid=sid)
#             print("shared var value is:" shared_var)
#         elif msg_type == 'answer':
#             if shared_var['state'] == 'broadcast':
#                 shared_var['target_peer'] = sid
#                 await sio.send(data, sid=shared_var['sid'])
#     #         forward_answer() #Forward only to the sid who had requested the offer
#                 print("shared var value is:" shared_var)
#         elif msg_type == 'ice-candidate':
#             if sid in [shared_var['sid'], shared_var['target_peer']]:
#                 await sio.send(data, sid=shared_var['sid'])
#                 print("shared var value is:" shared_var)








# WebRTC implementation


# Capture list of connectecd clients to the socket
connected_clients = {}
device_session_map = {} # holding sid --> DeviceId mapping {"<sid>": "<deviceID>"}
# signal_state = {'sid': '', 'state': '', 'target_peer': ''}
audit_signal = {
        'requestor_id':  '',
        'broadcasted_ids': [],
        'serving_peer':  '',
        'request_message': '',
        'reference_mapping': {}
    }

# TODO persist the audit signal state to DB once the chat has been estalished.
# def get_deviceID(device_id = '125'):
#     location_collection = get_location_collection()
#     location = location_collection.find_one({'DeviceID': device_id}, sort=[('Timestamp', -1)])
#     print("location data:", location)

def get_device_id(environ):
        query_string = environ.get('QUERY_STRING', '')
        query_params = {key: value for key, value in (item.split('=') for item in query_string.split('&') if '=' in item)}
        return query_params.get('DeviceID', None)

# PreOperation
@sio.event
async def connect(sid, environ):
    """
    Event handler once the connection has been setup to client
    """
    # Map deviceID with SID
    DeviceID = get_device_id(environ)
    device_session_map[sid] = DeviceID
    
    # connected_clients[sid]= {'sid': sid, 'environ': environ}
    # print("connected clients are:", device_session_map)
    # print("audit signal state:", audit_signal)
    await sio.emit('your_session_id', {'sid': sid}, to=sid)

    #Integrating socket IO events with api specific data
    

@sio.event
def disconnect(sid):
    if sid in device_session_map:
        del device_session_map[sid]
        print(device_session_map)
    if sid in [audit_signal['requestor_id'],audit_signal['serving_peer']]:
        audit_signal['serving_peer'] = ''
        audit_signal['requestor_id'] = ''
        audit_signal['broadcasted_ids'] = []
        # print(audit_signal)

async def on_answer(sid, data):
    """
    Redirect the response only to the customer for establishing the
    peer communication.
    """
    # if signal_state['state'] == 'broadcast':
    # print("audit_signal values at answer request:", audit_signal)
    if not audit_signal['serving_peer']: # if serving peer is empty, only then it enters into loop
        audit_signal['serving_peer'] = sid
        # signal_state['state'] = 'served'
        # print(f'ANSWER:Testing run time values - audit_signal: {audit_signal}, current-sid: {sid}')
        # print(datetime.now(), "message through signalling server:", data)
        await sio.send(data, to=audit_signal['requestor_id'])

def lookup_broadcast_peers(sid):
    """
    Lookup for broadcast peers based on the requestor profile in DB and the peers connected to sockets
    """
    remote_clients = []
    # Retrieve DeviceID from sid - check the connection event
    # Based on the deviceID, identify the location and Profile - JSON
    device_collection = get_device_collection()
    device_profile = device_collection.find_one({'DeviceID': device_session_map[sid]}, sort=[('Timestamp', -1)])
    available_network = list(device_session_map.values())
    remote_obj = device_collection.find(
        {
            'Location': device_profile['Location'], 
            'Profile': device_profile['Profile'],
            'DeviceID': {'$in': available_network}
        }
    )
    while remote_obj.alive:
        remote_clients.append(remote_obj.next()['DeviceID'])
    remote_clients.remove(device_session_map[sid])
    return remote_clients



async def broadcast_peers(sid, data, remote_clients):
    """
    Broadcast the messsage to the available users based on the 
    location, customer intent and priority.
    """
    remote_sids = [key for key, value in device_session_map.items() if value in remote_clients]
    #audit information
    audit_signal['requestor_id'] = sid
    audit_signal['broadcasted_ids'] = remote_sids
    audit_signal['reference_mapping'] = device_session_map
    print(f'OFFER:Testing run time values - audit_signal: {audit_signal}, current-sid: {sid}')
    for each_sid in remote_sids:
        print(datetime.now(), f"sending offer to sid:{each_sid}")
        await sio.send(data, to=each_sid)
    # await sio.send(data, skip_sid=sid)

# audit log for Signalling mechanism:
# create an event once the chat has been established - persisted to DB in auditLog

async def on_candidate(sid, data):
    """
    Handle ICE candidates generated during Session description protocol
    to exchange to only identified parties

    Establishes communication between both parties
    """
    if not audit_signal['serving_peer']: # if serving_peer is empty, broadcast to all the matching clients
        # print(datetime.now(),"message through signalling server:", data)
        await sio.send(data, to=audit_signal['broadcasted_ids'])
    else:
        # After offer/answer has been acknowledged - exchange candidates to only ideal partners
        if sid == audit_signal['requestor_id']:
            # print(datetime.now(),"message through signalling server:", data)
            # print("audited value:",audit_signal)
            await sio.send(data, to=audit_signal['serving_peer'])
        elif sid == audit_signal['serving_peer']:
            # print(datetime.now(),"message through signalling server:", data)
            # print("audited value:",audit_signal)
            await sio.send(data, to=audit_signal['requestor_id'])
        # print(signal_state)

    # if signal_state['state'] == 'broadcast':
    #     signal_state['target_peer'] = sid
    #     signal_state['state'] = 'served'
    #     print("message through signalling server:", data)
    #     await sio.send(data, to=signal_state['sid'])                

def reset_offer_audit():
    reset_audit_signal = {
        'requestor_id':  '',
        'broadcasted_ids': [],
        'serving_peer':  '',
        'request_message': '',
        'reference_mapping': {}
    }
    return reset_audit_signal

@sio.event
async def chat_established(sid):
    print("after chat has been established", audit_signal)

@sio.event
async def message(sid, data):
    """
    sid(str): holds socket session id from which event has been triggered
    data(str): event specific messages from client containing contracts(offer, answer)
            and ICE candidates

    Redirects the response to peers based on the signalling logic. 
    """
    if len(device_session_map.keys()) > 1:
        remote_clients = lookup_broadcast_peers(sid) # find the remote peers based on the client request
        if remote_clients:
            message = json.loads(data)
            msg_type = message['type']
            # print("signalling message:", message)
            if msg_type == 'offer':      
                # reset_offer_audit()
                # print("OFFER:AFTER AUDIT MESSAGE:::::::::::::::::::::::", audit_signal)          
                # audit_signal["sid"] = sid
                # signal_state["state"] = "broadcast"
                print("***************************Offer****************")
                def message_acknowledged():
                    print("Message was acknowledged by client")
                print(datetime.now(),"message through signalling server:", data)
                await broadcast_peers(sid, data, remote_clients)
                print("************************OfferEnd***********************")    
                # await sio.send(data, skip_sid=sid, callback=message_acknowledged)

            elif msg_type == 'answer':
                print("***************************answer****************")
                # print("ANSWER:AUDIT MESSAGE:::::::::::::::::::::::", audit_signal)   
                print(datetime.now(),"message through signalling server:", data)       
                await on_answer(sid, data) #Forward only to the sid who had requested the offer
                print("***************************answeEnd****************")
                    # await sio.send(data, to=signal_state['sid'])
                    # print(signal_state)
            elif msg_type == 'candidate':
                print("***************************candidate****************")
                print("CANDIDATE:AUDIT MESSAGE:::::::::::::::::::::::", audit_signal)
                print(f'Testing run time values - offer-sid: {audit_signal['requestor_id']}, target-sid: {audit_signal['serving_peer']}, current-sid: {sid}, message_type: {msg_type}')
                await on_candidate(sid, data)
                print("************************candidateEnd*******************")
                # if not signal_state['target_peer']:
                #     print(datetime.now(),"message through signalling server:", data)
                #     await sio.send(data, skip_sid=signal_state['sid'])
                # elif sid == signal_state['target_peer']:
                #     print(datetime.now(),"message through signalling server:", data)
                #     await sio.send(data, to=signal_state['sid'])
                    # print(signal_state)
            elif msg_type == 'dataChannelOpened':
                # ensuring the connected peers are removed from broadcast.
                # this event is triggered by remote client once the connection has been established
                if sid in device_session_map:
                    del device_session_map[sid]
                    del device_session_map[audit_signal['requestor_id']]
        else:
           print(device_session_map)
           await sio.emit('refine_request', to=sid)
           # TODO: ensure only single message is sent to client - currently two messages are sent - offer and candidate
    else:
        await sio.emit('no_peers', to=sid) # No peers has been found


# Application specific.
# TODO: Look to see whether we can integrate this with register API as part of signalling process.
@app.route('/api/device/register', methods=['POST'])
async def register_device():
    # TODO: Implement timeout for API's for unexpected delays due to exception handling
    data = await request.json
    print("data type of request:", data)
    # print("request args:",request.args)
    device_collection = get_device_collection()
    device_collection.insert_one({
        'DeviceID': data['DeviceID'],
        'Location': data['Location'],
        'Profile': data['Profile'],
        'LastSeenTimestamp': datetime.now()
    })
    return {'status': 'success'}, 201

# Api's for updating the location
@app.route('/api/device/location', methods=['POST'])
async def update_location():
    data = await request.json
    location_collection = get_location_collection()
    location_collection.insert_one({
        'DeviceID': data['DeviceID'],
        'Location': {
            'type': 'Point',
            'coordinates': [data['longitude'], data['latitude']]
        },
        'status': data['status'],
        'Timestamp': datetime.now()
    })
    return {'status': 'success'}, 201


# Api's for retrieving the location details
@app.route('/api/device/track', methods=['GET'])
async def track_device():
    print(request)
    device_id = request.args.get('DeviceID')
    location_collection = get_location_collection()
    location = location_collection.find_one({'DeviceID': device_id}, sort=[('Timestamp', -1)])
    return dumps(location)

# As part of updating the location, ensure whether it would help the user in establishing the broadcast.
# def insert_new_location(device_id, coordinates, endpoint, user_email):
#     """Insert a new location and check if it triggers a notification."""
#     locations.insert_one({
#         'DeviceID': device_id,
#         'Location': {
#             'type': 'Point',
#             'coordinates': coordinates
#         },
#         'Timestamp': datetime.now(),
#         'Endpoint': endpoint
#     })
#     # Example condition: Device enters a specific area
#     if coordinates == [specific_longitude, specific_latitude]:
#         send_notification(user_email, 'Device Alert', 'Your device has entered a designated area.')



# # Api's for broadcasting the message
# @app.route('/api/message/broadcast', methods=['POST'])
# def send_broadcast_message():
#     message = request.json['message']
#     endpoints = get_active_user_endpoints()  # Automatically fetch active endpoints
#     if not endpoints:
#         return jsonify({'error': 'No active users found.'}), 404
#     results = broadcast_message(message, endpoints)
#     return jsonify(results), 200    

async def main():
    config = Config()
    config.bind = ["0.0.0.0:8003"]
    config.debug = True
    config.reload = True  # Enable auto-reloading
    await hypercorn.asyncio.serve(app, config)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
