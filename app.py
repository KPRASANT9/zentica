# Exposing Zentica application
from quart import Quart, render_template_string, websocket, request, render_template
from quart_cors import cors
import socketio
from waitress import serve
import ssl

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
app = Quart(__name__, static_folder='static', static_url_path='/static')
app.config['DEBUG'] = True
app = cors(app)
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=['https://meet-basilisk-adversely.ngrok-free.app', '*'])
zentica_demo = socketio.ASGIApp(sio, app)
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
        return query_params

# PreOperation
@sio.event
async def connect(sid, environ):
    """
    Event handler once the connection has been setup to client
    """
    # Map deviceID with SID
    query_params = get_device_id(environ)
    DeviceID = query_params.get('DeviceID', None)
    # Location = query_params.get('Location', None)
    # REfine it at later point in time
    device_session_map[sid] = DeviceID
    
    # connected_clients[sid]= {'sid': sid, 'environ': environ}
    print("connected clients are:", device_session_map)
    print("audit signal state:", audit_signal)
    await sio.emit('your_session_id', {'sid': sid}, to=sid)

    #Integrating socket IO events with api specific data

@sio.event
async def disconnect(sid):
    if sid in device_session_map:
        del device_session_map[sid]
        print(device_session_map)
    if sid in [audit_signal['requestor_id'],audit_signal['serving_peer']]:
        audit_signal['serving_peer'] = ''
        audit_signal['requestor_id'] = ''
        audit_signal['broadcasted_ids'] = []
        # print(audit_signal)

@sio.event
async def update_location(sid, data):
    print(data)
    update_location(sid, data)        

async def update_location(sid, data):
    # data = await request.json
    message = json.loads(data)
    location_collection = get_location_collection()
    location_collection.update_one({
        'DeviceID': device_session_map[sid],
        'Location': {
            'type': 'Point',
            'coordinates': [message['coords']['latitude'], message['coords']['longitude']]
        }
    }, upsert=True)
    print('successfully updated the location data:', data)

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
        print(f'ANSWER:Testing run time values - audit_signal: {audit_signal}, current-sid: {sid}')
        print(datetime.now(), "message through signalling server:", data)
        await sio.send(data, to=audit_signal['requestor_id'])

async def lookup_broadcast_peers(sid, data):
    """
    Lookup for broadcast peers based on the requestor profile in DB and the peers connected to sockets
    """
    message = json.loads(data)
    print("Message body is", message)
    remote_clients = []
    # Retrieve DeviceID from sid - check the connection event
    # Based on the deviceID, identify the location and Profile - JSON
    device_collection = get_device_collection()
    # TODO ensure DeviceID is unique and duplicate values are not entered as part of registration from UI
    device_profile = device_collection.find_one({'DeviceID': device_session_map[sid]}, sort=[('Timestamp', -1)])
    print("device profile values:", device_profile)
    available_network = list(device_session_map.values())
    print(f"Debug issue - remote_clients: {remote_clients}, removing element: {device_session_map[sid]}", )
    # Make sure the requested client is not part of the peer selection while broadcasting
    available_network.remove(device_session_map[sid])
    remote_obj = device_collection.find(
        {
            'Location': device_profile['Location'], 
            'Profile': message['wishMessage'],
            'DeviceID': {'$in': available_network}
        }
    )
    if remote_obj.alive:
        for device in remote_obj:
            remote_clients.append(device['DeviceID']) 
    print("remote clients are", remote_clients)
    return remote_clients

@sio.event
async def onbroadcast(sid, data):
    print("broadcast event trigger has been called", data)
    remote_clients = await lookup_broadcast_peers(sid, data)
    remote_sids = [key for key, value in device_session_map.items() if value in remote_clients]
    audit_signal['requestor_id'] = sid
    audit_signal['broadcasted_ids'] = remote_sids
    audit_signal['reference_mapping'] = device_session_map
    print(f'OFFER:Testing run time values - audit_signal: {audit_signal}, current-sid: {sid}')
    for each_sid in remote_sids:
        print(datetime.now(), f"sending offer to sid:{each_sid}")
        await sio.send(data, to=each_sid)



# async def broadcast_peers(sid, data, remote_clients):
#     """
#     Broadcast the messsage to the available users based on the 
#     location, customer intent and priority.
#     """
#     print("OFFER: remote client values:", remote_clients)
#     remote_sids = [key for key, value in device_session_map.items() if value in remote_clients]
#     #audit information
#     audit_signal['requestor_id'] = sid
#     audit_signal['broadcasted_ids'] = remote_sids
#     audit_signal['reference_mapping'] = device_session_map
#     print(f'OFFER:Testing run time values - audit_signal: {audit_signal}, current-sid: {sid}')
#     for each_sid in remote_sids:
#         print(datetime.now(), f"sending offer to sid:{each_sid}")
#         await sio.send(data, to=each_sid)
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
            print(datetime.now(),"message through signalling server:", data)
            print("audited value:",audit_signal)
            await sio.send(data, to=audit_signal['serving_peer'])
        elif sid == audit_signal['serving_peer']:
            print(datetime.now(),"message through signalling server:", data)
            print("audited value:",audit_signal)
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
    print("Message receieved at Signalling Mechanism:", data)
    print("device sesssion map values are:", device_session_map)
    if len(device_session_map.keys()) > 1:
        remote_clients = audit_signal['broadcasted_ids']
        if remote_clients:
            message = json.loads(data)
            msg_type = message['type']
            # print("signalling message:", message)
            # if msg_type == 'offer':      
            #     # reset_offer_audit()
            #     # print("OFFER:AFTER AUDIT MESSAGE:::::::::::::::::::::::", audit_signal)          
            #     # audit_signal["sid"] = sid
            #     # signal_state["state"] = "broadcast"
            #     print("***************************Offer****************")
            #     def message_acknowledged():
            #         print("Message was acknowledged by client")
            #     print(datetime.now(),"message through signalling server:", data)
            #     await broadcast_peers(sid, data, remote_clients)
            #     print("************************OfferEnd***********************")    
            #     # await sio.send(data, skip_sid=sid, callback=message_acknowledged)

            if msg_type == 'answer':
                print("***************************answer****************")
                print("ANSWER:AUDIT MESSAGE:::::::::::::::::::::::", audit_signal)   
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
                print("chat has been established")
                for device in (sid, audit_signal['requestor_id']):
                    await sio.emit('oncommunicator', to=device)
                if sid in device_session_map:
                    del device_session_map[sid]
                    # del device_session_map[audit_signal['requestor_id']]
        else:
            await sio.emit('refine_request', to=sid) # No peers has been found
    else:
        await sio.emit('no_peers', to=sid) # No peers has been found

# Blocking issues
@app.after_request
async def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "upgrade-insecure-requests"
    return response

# Application specific.
@app.route('/')
async def landing():
    return await app.send_static_file('registration.html')

@app.route('/client')
async def communication():
    return await app.send_static_file('client.html')

@app.route('/genie')
async def genie_communication():
    return await app.send_static_file('genie.html')

# @app.route('/communicator')
# async def chat_communication():
#     return await app.send_static_file('communicator.html')            

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
# @app.route('/api/device/location', methods=['POST'])


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
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(certfile='/Users/prasanthkarlaa/Desktop/Zentica/zentica/cert/localhost+2.pem', keyfile='/Users/prasanthkarlaa/Desktop/Zentica/zentica/cert/localhost+2-key.pem')
    config = Config()
    # config.bind = ["0.0.0.0:8003"]
    config.debug = True
    config.reload = True  # Enable auto-reloading
    await hypercorn.asyncio.serve(app, config, port=8443, ssl_context=ssl_context)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
