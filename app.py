# Exposing Zentica application
from quart import Quart, render_template_string, websocket, request, render_template
from quart_cors import cors
import socketio
from waitress import serve
import ssl

#Real time communication
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCIceCandidate, RTCDataChannel

# Application specific
from db import get_device_collection, get_location_collection

# LLM specific
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Generic Packages
from datetime import datetime, timedelta
import time
from bson.json_util import dumps
import json
from bidict import bidict
import itertools

# schedulers
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from asyncio import Lock
import asyncio

from dotenv import load_dotenv
import os

from math import radians, sin, cos, sqrt, asin

import logging
import sys
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

# Create Quart app

app = Quart(__name__, static_folder='static', static_url_path='/static')
app.config['DEBUG'] = True
app = cors(app)
scheduler = AsyncIOScheduler()  # Scheduler initialization
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
#         logger.debug("connect ", sid, self.shared_var)

#     def disconnect(self, sid):
#         logger.debug("disconnect ", sid, self.shared_var)

#     def message(self, sid, data):
#         message = json.loads(data)
#         msg_type = message['type']
#         if msg_type == 'offer':
#             shared_var = {"sid": sid, "state": "broadcast"}
#     #         handle_offer() # Broadcast the offer to rest of the connected clients except sender(Use SID from the event)
#             await sio.send(data, skip_sid=sid)
#             logger.debug("shared var value is:" shared_var)
#         elif msg_type == 'answer':
#             if shared_var['state'] == 'broadcast':
#                 shared_var['target_peer'] = sid
#                 await sio.send(data, sid=shared_var['sid'])
#     #         forward_answer() #Forward only to the sid who had requested the offer
#                 logger.debug("shared var value is:" shared_var)
#         elif msg_type == 'ice-candidate':
#             if sid in [shared_var['sid'], shared_var['target_peer']]:
#                 await sio.send(data, sid=shared_var['sid'])
#                 logger.debug("shared var value is:" shared_var)






# WebRTC implementation

load_dotenv()
api_key = os.getenv("OPEN_AI_KEY")

device_session_map = bidict({}) # holding sid --> DeviceId mapping {"<sid>": "<deviceID>"}

class EventGraph:
    def __init__(self):
        self.graph = {}
        self.reverse_graph = {}
        self.event_states = {}
        self.shared_variables = {}

    def add_event(self, cause, effect, state=None):
        if cause not in self.graph:
            self.graph[cause] = []
        self.graph[cause].append(effect)
        if effect not in self.reverse_graph:
            self.reverse_graph[effect] = []
        self.reverse_graph[effect].append(cause)
        if effect not in self.event_states:
            self.event_states[effect] = {}
        if state:
            self.event_states[effect].update(state)

    def get_causes(self, effect):
        return self.reverse_graph.get(effect, [])
    
    def get_effects(self, cause):
        return self.graph.get(cause, [])
    
    def get_lineage(self, effect, lineage=None):
        if lineage is None:
            lineage = []
        causes = self.get_causes(effect)
        if not causes:  # Base case: no parents found
            return lineage
        for cause in causes:
            lineage.append(cause)
            self.get_lineage(cause, lineage)
        return lineage
    
    def get_event_state(self, event):
        return self.event_states.get(event, {})
    
    def update_event_state(self, event, state_update):
        if event in self.event_states:
            self.event_states[event].update(state_update)
        else:
            self.event_states[event] = state_update

    def get_shared_variable(self, variable_name):
        return self.shared_variables.get(variable_name)
    
    def update_shared_variable(self, variable_name, value):
        self.shared_variables[variable_name] = value

    def to_dict(self):
        return {
            "graph": self.graph,
            "reverse_graph": self.reverse_graph,
            "event_states": self.event_states,
            "shared_variables": self.shared_variables
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
    
    @classmethod
    def from_dict(cls, data):
        instance = cls()
        instance.graph = data.get("graph", {})
        instance.reverse_graph = data.get("reverse_graph", {})
        instance.event_states = data.get("event_states", {})
        instance.shared_variables = data.get("shared_variables", {})
        return instance

    @classmethod
    def from_json(cls, json_string):
        data = json.loads(json_string)
        return cls.from_dict(data)
    
event_graph = EventGraph()

#Scheduler to refresh the state of the system
async def poll_audit_events():
    # logger.debug("Scheduler is working as expected!!")
    global event_graph
    # logger.debug("scheduler: event graph state:", event_graph.to_dict())
    if 'retention_time' in event_graph.shared_variables:
        # logger.debug('successfully navigated to inner loop of scheduler')
        if (datetime.now() > event_graph.get_shared_variable('retention_time')):
            # logger.debug("event sent for the client for his request:", device_session_map.inverse[audit_signal['requestor_id']])
            if 'serving_id' not in event_graph.shared_variables:
                await sio.emit('no_peers', to=device_session_map[event_graph.get_shared_variable('client_id')])
            event_graph = EventGraph()

# TODO persist the audit signal state to DB once the chat has been estalished.

def get_device_id(environ):
        query_string = environ.get('QUERY_STRING', '')
        query_params = {key: value for key, value in (item.split('=') for item in query_string.split('&') if '=' in item)}
        return query_params

def find_matching_category(wishMessage, available_category):
    """
    Based on the wish message, it return the available sector matching the profile.
    """
    
    # prompt message for categorizing the user request:
    json_schema = {
        "title": "Sector",
        "description": "information about sector name",
        "type": "object",
        "properties": {
            "sector": {
                "title": "category",
                "description": "The sector name",
                "type": "string",
                "enum": available_category,
                "default": 'other'
            }
        },
        "required": "sector"
    }
    dumps = json.dumps(json_schema, indent=2)
    messages = [
        HumanMessage(
            content="Please tell me about a sector name using the following JSON schema:"
        ),
        HumanMessage(content=f"{dumps}"),
        HumanMessage(
            content=f"Now, considering the schema, tell me about a sector name for {wishMessage}. response in json format"
        ),
    ]
    prompt = ChatPromptTemplate.from_messages(messages)
    # llm = ChatOllama(model="llama3")
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=api_key)#, max_tokens = 25)
    chain = prompt | llm | StrOutputParser()
    matching_network = chain.invoke({"dumps": dumps, "wishMessage": wishMessage})
    logger.debug(f"Accepted values for LLM: Input - {wishMessage}, response - {matching_network}")
    logger.debug(matching_network)
    return json.loads(matching_network)['sector']

async def on_answer(sid, data):
    """
    Redirect the response only to the customer for establishing the
    peer communication.
    """
    # if signal_state['state'] == 'broadcast':
    if 'serving_id' not in event_graph.shared_variables: # if serving peer is empty, only then it enters into loop
        event_graph.update_shared_variable('serving_id', device_session_map.inverse[sid])
        # event_graph.update_shared_variable('transit_network', event_graph.get_lineage(device_session_map[sid]))
        # signal_state['state'] = 'served'
        # logger.debug(datetime.now(), "message through signalling server:", data)
        await sio.send(data, to=device_session_map[event_graph.get_shared_variable('client_id')])

def lookup_location(origin, message_obj, target):

    "Returns boolean based on the matching condition for radius among two devices"

    # Making a precision of 5 decimals to eensure the exact location difference is captured
    radius = format(float(message_obj['broadcastRange']), ".5f")

    def haversine(lat1, lon1, lat2, lon2):
        # Haversine formula to calculate distance between two points on Earth
        R = 3959  # average earth radius in miles
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        delta_lat = lat2 - lat1
        delta_lon = lon2 - lon1
        a = sin(delta_lat / 2)**2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2)**2
        c = 2 * asin(sqrt(a))
        logger.debug(f'value of c is,{c}')
        return str(R * c)

    origin_lat, origin_long = event_graph.get_event_state(origin)['lct']
    target_lat, target_long = event_graph.get_event_state(target)['lct']
    distance = haversine(origin_lat, origin_long, target_lat, target_long)
    logger.debug(f'The distance between two devices - {origin} & {target} is: {distance}')
    logger.debug(f'given radius value is - {radius}: {float(distance) <= float(radius)}')
    return float(distance) <= float(radius)

def lookup_peers(sid, event_graph, available_peers):
    """
    Lookup for broadcast peers based on the requestor profile in DB and the peers connected to sockets

    convention: ensure lookups are validated. Would contain bool values.

    Args:
        available_peers[list] - list of available peers connected to socket(holds single item or multiple items as a list)
        event_graph[class] - holding the state of the entire event graph
    return:
        remote_peers[list] - Ideal candidates after filtering the location and profile mapping
    """
    message_obj = json.loads(event_graph.get_shared_variable('offer'))
    device_id = device_session_map.inverse[sid]
    logger.debug(f'Message body is {message_obj}')
    # remote_clients = []
    # Retrieve DeviceID from sid - check the connection event
    # Based on the deviceID, identify the location and Profile - JSON
    device_collection = get_device_collection()
    # TODO ensure DeviceID is unique and duplicate values are not entered as part of registration from UI
    # TODO RAG Augmemented profile needs to be pulled to check for contraints going forward
    # device_profile = device_collection.find_one({'DeviceID': device_session_map[sid]}, sort=[('Timestamp', -1)])
    # logger.debug("device profile values:", device_profile)

    # available_network = list(device_session_map.values())
    # logger.debug(f"Debug issue - remote_clients: {remote_clients}, removing element: {device_session_map[sid]}")
    # Make sure the requested client is not part of the peer selection while broadcasting
    logger.debug(f'List of available peers:{available_peers}')
    logger.debug(f'event graph state values are: {event_graph.to_dict()}')
    

    # If the event is triggered through UI(human or recursive), Broadcasting to their specific locations are enabled
    location_network = []
    remote_network = []
    for remote_peer in available_peers:
        if event_graph.get_causes(device_id):
            if lookup_location(device_id, message_obj, remote_peer):
                location_network.append(remote_peer)
        else:
            # for the newly joined device, the location is validated with the existing event device network
            # In this scenario, we would mostly contain only one remote peer which is the newly joined device that is planning to validate within the session
            for device_network in list(event_graph.graph.keys()):
                if lookup_location(remote_peer, message_obj, device_network):
                    location_network.append(remote_peer)
                    break;
                elif remote_peer in device_collection.find_one({"DeviceID": device_network})['Network']:
                    remote_network.append(remote_peer)
                    break;

    if event_graph.get_causes(device_session_map.inverse[sid]):
        #Bypassing location based rules for estalished network to create a chain of communication
        remote_network = device_collection.find_one({"DeviceID": device_session_map.inverse[sid]})
        if remote_network['Network']:
            remote_network = list(itertools.chain.from_iterable(remote_network['Network']))

    if (location_network or remote_network):
        # profiling devices based on the wishmessage, TODO: refine based on the constraints provided.
        remote_obj = device_collection.find(
            {
                # ensure time, location, person(constraint) based filtering is done.
                'Profile': event_graph.get_shared_variable('category'),
                'DeviceID': {'$in': location_network + remote_network}
            }
        )
        if remote_obj.alive:
            remote_peers = []
            for device in remote_obj:
                remote_peers.append(device['DeviceID']) 
        logger.debug(f'remote clients are: {remote_peers}')
        return remote_peers
    else:
        return []


async def notify_peers(sid, event_graph, remote_clients):
    """An offer is associated with multiple candidate sdp for it to communicate across various streams"""
    
    data = event_graph.get_shared_variable('offer')
    device_id = device_session_map.inverse[sid]
    broadcast_network = []

    if event_graph.get_causes(device_id):
        broadcasted_network = []
        for parent in event_graph.get_causes(device_id):
            if ('broadcast_ids' in event_graph.get_event_state(parent)):
                broadcasted_network +=  event_graph.get_event_state(parent)['broadcast_ids']
        # Broadcasted clients part of previus event states are not involved
        remote_clients = list(set(remote_clients) -  set(broadcasted_network)) 

    for peer in remote_clients:
        if device_session_map[peer]:
            broadcast_network.append(peer)
            event_graph.add_event(device_session_map.inverse[sid], peer)
            logger.debug(f'{datetime.now()} sending offer to sid: {device_session_map[peer]}')
            # send offer to matching peer
            await sio.send(data, to=device_session_map[peer])
            # send candidates to matching peer
            logger.debug("event graph during initiating candiate:", event_graph.to_dict())
            if 'candidate' in event_graph.shared_variables:
                for sdp in event_graph.get_shared_variable('candidate'):
                    await sio.send(sdp, to=device_session_map[peer])
    event_graph.update_event_state(device_session_map.inverse[sid], {'referrence_mapping': device_session_map, 'broadcast_ids': broadcast_network})

async def lookup_notify_peers(sid, event_graph, connected_network):
    """Based on the audit event, will lookup based on filter conditioins and notify the user"""
    remote_peers = lookup_peers(sid, event_graph, connected_network)
    if remote_peers:
        await notify_peers(sid, event_graph, remote_peers)    

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
    device_session_map[DeviceID] = sid 
    
    logger.debug(f'connected clients are: {device_session_map}')
    logger.debug(f'event graph signal state: {event_graph.to_dict()}')
    await sio.emit('your_session_id', {'sid': sid}, to=sid)

@sio.event
async def join_broacast(sid):
    """
    Ability to join the broadcast initiative if it has any parent event
    """
    device_id = device_session_map.inverse[sid]
    cause_event = event_graph.get_causes(device_id)
    if cause_event:
        event_graph.add_event(cause_event, device_id)
        connected_network = list(device_session_map.keys())
        connected_network.remove(device_id)
        lookup_notify_peers(sid, event_graph, connected_network)
    # ability to join the broadcast and lookout for peers

@sio.event
async def disconnect(sid):
    logger.debug("disconnect: event graph state:", event_graph.to_dict())
    # if device_session_map[sid] in [event_graph.get_shared_variable('client_id'), event_graph.get_shared_variable('serving_id')]:
    #     event_graph = EventGraph()
    if sid in device_session_map.values():
        if event_graph.event_states:
            del event_graph.event_states[device_session_map.inverse[sid]]
        del device_session_map.inverse[sid]
        logger.debug(f'After disconnection - dsm: {device_session_map}')

@sio.event
async def update_location(sid, message):
    '''
    data holds the list with [lat, long]
    '''
    device_id = device_session_map.inverse[sid]
    msg_obj = json.loads(message)
    logger.debug(f'device location coordinates are: {msg_obj}')
    event_graph.update_event_state(device_id, {'lct': msg_obj['data']})
    # ensuring the remote clients are served for the existing request.
    if event_graph.get_shared_variable('client_id'):
        if (device_id != event_graph.get_shared_variable('client_id') and not event_graph.get_shared_variable('serving_id')):
            await lookup_notify_peers(sid, event_graph, [device_session_map.inverse[sid]])         

# async def update_location(sid, data):
#     # data = await request.json
#     message = json.loads(data)
#     location_collection = get_location_collection()
#     location_collection.update_one({
#         'DeviceID': device_session_map[sid],
#         'Location': {
#             'type': 'Point',
#             'coordinates': (message['coords']['latitude'], message['coords']['longitude'])
#         }
#     }, upsert=True)
#     logger.debug('successfully updated the location data:', data)

@sio.event
async def onbroadcast(sid, data):
    logger.debug("broadcast event trigger has been called", data)

    data_obj = json.loads(data)

    # Creating an instance for eventGraph to track the state of the request
    # event_graph = EventGraph()

    # Adding network as part of broadcast to the device profile
    if 'addNetwork' in data_obj:
        device_collection = get_device_collection()
        device_collection.find_one_and_update(
            {"DeviceID": device_session_map.inverse[sid]},  
            {"$addToSet": {"Network": data_obj['addNetwork']}}
        )

    # using LLM to classify the category for the request
    available_category = ["Healthcare", "Education", "Technology", "Hospitality", "Finance", "Retail", "Transportation", "Professional", "Arts", "Manufacturing", "Marketing", "Public", "Retail", "Agriculture", "Environmental", "Other"]
    assigned_category = find_matching_category(data_obj['wishMessage'], available_category)
    logger.debug(f"LLM into ACTION: for the wish message: {data_obj['wishMessage']}, the assigned category is: {assigned_category}")
    
    # Log broadcast event to audit_signal
    event_graph.add_event(device_session_map.inverse[sid], device_session_map.inverse[sid])
    event_graph.update_shared_variable('time_stamp', str(datetime.now()))
    event_graph.update_shared_variable('client_id', device_session_map.inverse[sid])                                            #audit_signal['requestor_id'] = device_session_map[sid] 
    event_graph.update_shared_variable('offer', data)                                                           #audit_signal['request_message']['offer'] = data 
    event_graph.update_shared_variable('category', assigned_category)                                          # audit_signal['request_category'] = assigned_category 
    # event_graph.update_shared_variable('transit_network', assigned_category)                                            #audit_signal['transit_nework'].append(device_session_map[sid]) 
    event_graph.update_shared_variable('retention_time', datetime.now() + timedelta(minutes=int(data_obj['broadcastTime']))) #audit_signal['retention_time'] =  

    connected_network = list(device_session_map.keys())
    connected_network.remove(device_session_map.inverse[sid])

    if connected_network:
        await lookup_notify_peers(sid, event_graph, connected_network)
    # remote_sids = [key for key, value in device_session_map.items() if value in remote_clients]
    
    # logger.debug(f'OFFER:Testing run time values - audit_signal: {audit_signal}, current-sid: {sid}')
    
    # for each_sid in remote_sids:
    #     logger.debug(datetime.now(), f"sending offer to sid:{each_sid}")
    #     await sio.send(data, to=each_sid)


# async def broadcast_peers(sid, data, remote_clients):
#     """
#     Broadcast the messsage to the available users based on the 
#     location, customer intent and priority.
#     """
#     logger.debug("OFFER: remote client values:", remote_clients)
#     remote_sids = [key for key, value in device_session_map.items() if value in remote_clients]
#     #audit information
#     audit_signal['requestor_id'] = sid
#     audit_signal['broadcasted_ids'] = remote_sids
#     audit_signal['reference_mapping'] = device_session_map
#     logger.debug(f'OFFER:Testing run time values - audit_signal: {audit_signal}, current-sid: {sid}')
#     for each_sid in remote_sids:
#         logger.debug(datetime.now(), f"sending offer to sid:{each_sid}")
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
    device_id = device_session_map.inverse[sid]
    
    if device_id == event_graph.get_shared_variable('client_id'):
        logger.debug(f'{datetime.now()} message through signalling server: {data}')
        if 'candidate' not in event_graph.shared_variables:
            event_graph.update_shared_variable('candidate', [])
        event_graph.get_shared_variable('candidate').append(data)
        # logger.debug("audited value:",audit_signal)
        if 'serving_id' in event_graph.shared_variables:
            logger.debug(f'{datetime.now()} serving candidate to ideal peer: {data}')
            await sio.send(data, to=device_session_map[event_graph.get_shared_variable('serving_id')])
        elif 'broadcast_ids' in event_graph.get_event_state(device_id):
            logger.debug(f'{datetime.now()} serving candidate to braodcast peer: {data}')
            for device in event_graph.get_event_state(device_id)['broadcast_ids']:
                await sio.send(data, to=device_session_map[device])
    elif device_id == event_graph.get_shared_variable('serving_id'):
        logger.debug(f'{datetime.now()} message through signalling server: {data}')
        # logger.debug("audited value:",audit_signal)
        if 'client_id' in event_graph.shared_variables:
            await sio.send(data, to=device_session_map[event_graph.get_shared_variable('client_id')])
    # logger.debug("audit signal values are:", audit_signal)
        # logger.debug(signal_state)

    # if signal_state['state'] == 'broadcast':
    #     signal_state['target_peer'] = sid
    #     signal_state['state'] = 'served'
    #     logger.debug("message through signalling server:", data)
    #     await sio.send(data, to=signal_state['sid'])

@sio.event
async def chat_established(sid):
    logger.debug("after chat has been established")

@sio.event
async def message(sid, data):
    """
    sid(str): holds socket session id from which event has been triggered
    data(str): event specific messages from client containing contracts(offer, answer)
            and ICE candidates

    Redirects the response to peers based on the signalling logic. 
    """
    logger.debug(f'Message receieved at Signalling Mechanism: {data}')
    logger.debug(f'device sesssion map values are: {device_session_map}')
    # logger.debug("audit signal values are:", audit_signal)
    # if len(device_session_map.keys()) > 1:
        # remote_clients = audit_signal['broadcasted_ids']
        # if remote_clients:
    message = json.loads(data)
    msg_type = message['type']
    # logger.debug("signalling message:", message)
    # if msg_type == 'offer':      
    #     # reset_offer_audit()
    #     # logger.debug("OFFER:AFTER AUDIT MESSAGE:::::::::::::::::::::::", audit_signal)          
    #     # audit_signal["sid"] = sid
    #     # signal_state["state"] = "broadcast"
    #     logger.debug("***************************Offer****************")
    #     def message_acknowledged():
    #         logger.debug("Message was acknowledged by client")
    #     logger.debug(datetime.now(),"message through signalling server:", data)
    #     await broadcast_peers(sid, data, remote_clients)
    #     logger.debug("************************OfferEnd***********************")    
    #     # await sio.send(data, skip_sid=sid, callback=message_acknowledged)

    if msg_type == 'answer':
        logger.debug("***************************answer****************")
        # logger.debug("ANSWER:AUDIT MESSAGE:::::::::::::::::::::::", audit_signal)   
        logger.debug(f'{datetime.now()}, message through signalling server: {data}')       
        await on_answer(sid, data) #Forward only to the sid who had requested the offer
        logger.debug("***************************answeEnd****************")
            # await sio.send(data, to=signal_state['sid'])
            # logger.debug(signal_state)
    elif msg_type == 'candidate':
        logger.debug("***************************candidate****************")
        # logger.debug("CANDIDATE:AUDIT MESSAGE:::::::::::::::::::::::", audit_signal)
        # logger.debug(f'Testing run time values - offer-sid: {audit_signal['requestor_id']}, target-sid: {audit_signal['serving_peer']}, current-sid: {sid}, message_type: {msg_type}')
        await on_candidate(sid, data)
        logger.debug("************************candidateEnd*******************")
        # if not signal_state['target_peer']:
        #     logger.debug(datetime.now(),"message through signalling server:", data)
        #     await sio.send(data, skip_sid=signal_state['sid'])
        # elif sid == signal_state['target_peer']:
        #     logger.debug(datetime.now(),"message through signalling server:", data)
        #     await sio.send(data, to=signal_state['sid'])
            # logger.debug(signal_state)
    elif msg_type == 'dataChannelOpened':
        # ensuring the connected peers are removed from broadcast.
        # this event is triggered by remote client once the connection has been established
        logger.debug("chat has been established")
        global event_graph
        for device in (sid, device_session_map[event_graph.get_shared_variable('client_id')]):
            event_graph = EventGraph()
            await sio.emit('oncommunicator', to=device)
        # if sid in device_session_map:
        #     del device_session_map[sid]
            # del device_session_map[audit_signal['requestor_id']]
        # else:
        #     await sio.emit('refine_request', to=sid) # No peers has been found
    # else:
    #     await sio.emit('no_peers', to=sid) # No peers has been found

# Blocking issues
# @app.after_request
# async def add_security_headers(response):
#     response.headers['Content-Security-Policy'] = "upgrade-insecure-requests"
#     return response

@app.before_serving
async def start_scheduler():
    asyncio.get_event_loop().call_later(1, scheduler.start)  # Ensure scheduler starts in the same loop
    scheduler.add_job(poll_audit_events, 'interval', seconds=60)    

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
    logger.debug(f'data type of request: {data}')
    # logger.debug("request args:",request.args)
    device_collection = get_device_collection()
    device_collection.insert_one({
        'DeviceID': data['DeviceID'],
        'Profile': data['Profile'],
        'Network': [],
        'LastSeenTimestamp': datetime.now()
    })
    return {'status': 'success'}, 201

@app.route('/api/device/update', methods=['POST'])
async def update_device():
    # TODO: Implement timeout for API's for unexpected delays due to exception handling
    data = await request.json
    logger.debug(f'data type of request: {data}')
    # logger.debug("request args:",request.args)
    device_collection = get_device_collection()
    device_collection.find_one_and_update(
        {"DeviceID": data['DeviceID']},  # Query to find the document
        {"$addToSet": {"Network": data['networkID']}}  # Update operation
    )
    return {'status': 'success'}, 201
# Api's for updating the location
# @app.route('/api/device/location', methods=['POST'])

# Api's for listing the profile
@app.route('/api/device/list', methods=['GET'])
async def list_devices():
    total_devices = []
    device_collection = get_device_collection()
    for device_id in  device_collection.find():
        total_devices.append(device_id['DeviceID'])
    return dumps(total_devices)

# Api's for retrieving the location details
@app.route('/api/device/track', methods=['GET'])
async def track_device():
    logger.debug(request)
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

    #Add a scheduler to refresh auditsignal events
    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_audit_events, 'interval', seconds=5)
    scheduler.start()

    await hypercorn.asyncio.serve(app, config, port=8443, ssl_context=ssl_context)

    # server = await hypercorn.asyncio.start_server(app, config, port=8443, ssl_context=ssl_context)
    


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())