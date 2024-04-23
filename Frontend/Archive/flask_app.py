# Asynchronous operation compatible with Flask
# import eventlet
# eventlet.monkey_patch()

# Exposing Services
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS

#Real time communication

# Application specific
from db import get_device_collection, get_location_collection, get_active_user_endpoints
from broadcast import broadcast_message

#Generic Packages
from datetime import datetime
from bson.json_util import dumps

# asynchronous event loop


# Initialization
app = Flask(__name__)
CORS(app)
# socketio = SocketIO(app, cors_allowed_origins="*")




# WebRTC implementation

# PreOperation
# @sio.event
# def connect(sid, environ):
#     print("Client connected:", sid)
#     print("Environment:", environ)
#     sio.emit('message', {'data': 'Connected'})

# # Implementing webRTC protocol

# # Establishing RTCPeerConnection - offer and answer

# pcs = set()  # Keep track of all peer connections


# # 
# # def async_handle_offer(data):
# #     asyncio.create_task(handle_offer(data))


# @sio.event
# async def offer(sid, data): # add async
#     print('received offer!! Yes its working')
#     pc = RTCPeerConnection()
#     pc_id = "PeerConnection(%s)" % id(pc)
#     pcs.add(pc)
    
#     # Testing ice functionality

#     # if (pc.iceConnectionState):
#     #     print("inside ICE logic")
#     #     candidate = RTCIceCandidate(data['candidate'])
#     #     try:
#     #         pc.addIceCandidate(candidate)
#     #     except exception as error:
#     #         print("Failed to set ice candidate:", error)

#     @pc.on("iceconnectionstatechange")
#     async def on_iceconnectionstatechange():
#         print("%s ICE connection state is %s" % (pc_id, pc.iceConnectionState))
#         print("The PC state is", pc.on('datachannel'))
#         if pc.iceConnectionState == "failed":
#             await pc.close()
#             pcs.discard(pc)
#         elif pc.iceConnectionState == "connected":
#             print("Connection has been established")

#     # @pc.on("datachannel")
#     # async def on_datachannel():
#     #     print("Hello")

#     # Handle Data Channel creation by remote peer
#     @pc.on("datachannel")
#     def on_datachannel(channel: RTCDataChannel):
#         print(f"Data channel received: {channel.label}")

#         # Set event handlers for the data channel
#         @channel.on("open")
#         def on_open():
#             print(f"Data channel {channel.label} opened by remote peer.")

#         @channel.on("message")
#         def on_message(message):
#             print(f"Message received on next update {channel.label}: {message}")
#             channel.send("Thanks for the messsage!!")



#         @channel.on("close")
#         def on_close():
#             print(f"Data channel {channel.label} closed.")
    
#     # once connection has been established between client and a Flask server using aiortc, start communicaation using webRTC
#     # Setup Media streams(audio/video) and setup data channels
#     # data_channel = pc.createDataChannel("chat")
    
#     # @data_channel.on("open")
#     # def on_data_channel_open():
#     #     # print("data channel ready state", data_channel.readyState)
#     #     print("Data channel is open and ready to be used.")
#     #     data_channel.send('Hello')
#     # @data_channel.on('message')
#     # def on_message(message):
#     #     print("Received message:", message)

#     # @data_channel.on("close")
#     # def on_data_channel_close():
#     #     print("Data channel has been closed.")

#     # @data_channel.on("error")
#     # def on_data_channel_error(error):
#     #     print("Data Channel Error:", error)
    

#     # Set remote description
#     try:
#         remote_description = RTCSessionDescription(sdp=data['sdp'], type=data['type'])
#         await pc.setRemoteDescription(remote_description)
#         print("Remote description set successfully.")
#     except Exception as error:
#         print("Failed to set remote description:", error)

#     print("printing the remote description sdp from PC:", pc.remoteDescription.sdp)
    
    
#     # Assume we add some media tracks here or handle data channels
#     # Prepare local tracks if needed (we can use MediaStreamTrack subclasses here)
#     # pc.addTrack(...)

#     try:

#         answer = await pc.createAnswer() # add await
#         await pc.setLocalDescription(answer) # add await
#         print("local description set successfully.")
#     except Exception as error:
#         print("Failed to set local description:", error)

#     # await pc.close()
#     print("Printing local description sdp", pc.localDescription.sdp)
#     # Send answer back to client
#     await sio.emit('answer', {'sdp': pc.localDescription.sdp, 'type': pc.localDescription.type}); # add await
#     print("successfully emitted thee data from intital hand shake")

# # Enhance signalling and ICE process
# # TODO specific to appication domain - Create a session, retrieve records based on the available users and emit the message as an answeer to join the session

# #signaling purpose

# # Signaling: Both setLocalDescription and setRemoteDescription are integral to the signaling process in WebRTC, which is essential for initiating and maintaining communication sessions. Signaling is used to exchange information on how to connect, including session control messages to open or close communication, error messages, media metadata, network data (like IP addresses and ports), and more.
# # Negotiation: These methods help in negotiating the media and network configurations between peers, a process known as signaling negotiation or offer/answer negotiation.

# # users = {}  # Dictionary to store user status and information


# # @app.route('/register', methods=['POST'])
# # def register_user():
# #     user_id = request.json['user_id']
# #     users[user_id] = {'status': 'available'}
# #     return jsonify({"message": "User registered successfully"}), 200

# @sio.event
# async def session_available(sid, data):
#     # Notify specific user that a session is available
#     user_id = data['user_id']
#     if user_id in users and users[user_id]['status'] == 'available':
#         emit('join_session', {'message': 'Please join the session'}, room=user_id)



# # @socketio.on('message')
# # def handle_message(data):
# #     # print(message.type)
# #     # if (message.type == 'offer'):
# #     #     print('offer received')
# #     print('Received message:', data)
# #     socketio.send("Hello from Flask!")





# PostOperation
# @socketio.on('disconnect')
# def test_disconnect():
#     print('Client disconnected')


# Application specific.
# TODO: Look to see whether we can integrate this with register API as part of signalling process.
@app.route('/api/device/register', methods=['POST'])
def register_device():
    data = request.json
    print(data)
    device_collection = get_device_collection()
    device_collection.insert_one({
        'DeviceID': data['DeviceID'],
        'Location': data['Location'],
        'Profile': data['Profile'],
        'LastSeenTimestamp': datetime.now()
    })
    return jsonify({'status': 'success'}), 201

# Api's for updating the location
@app.route('/api/device/location', methods=['POST'])
def update_location():
    data = request.json
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
    return jsonify({'status': 'success'}), 201

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

# Api's for tracking the location
@app.route('/api/device/track', methods=['GET'])
def track_device():
    print("Success")
    device_id = request.args.get('DeviceID')
    print(device_id)
    location_collection = get_location_collection()
    location = location_collection.find_one({'DeviceID': device_id}, sort=[('Timestamp', -1)])
    print(location)
    return dumps(location)

# Api's for broadcasting the message
@app.route('/api/message/broadcast', methods=['POST'])
def send_broadcast_message():
    message = request.json['message']
    endpoints = get_active_user_endpoints()  # Automatically fetch active endpoints
    if not endpoints:
        return jsonify({'error': 'No active users found.'}), 404
    results = broadcast_message(message, endpoints)
    return jsonify(results), 200    


if __name__ == '__main__':
    # socketio.run(app, debug=True)
    # import hypercorn.asyncio
    # config = hypercorn.Config()
    # config.bind = ["0.0.0.0:5000"]
    # config.debug = True
    # hypercorn.asyncio.run(socketio_app, config)
    # import asyncio
    # asyncio.run(main())
    app.run(debug=True)
