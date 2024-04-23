document.addEventListener('DOMContentLoaded', function () {
    const wishMessage = document.getElementById('wish');
    const bidValue = document.getElementById('bid-value');
    const broadcastButton = document.getElementById('broadcast');  
    const consoleElement = document.getElementById('output');
    const params = new URLSearchParams(window.location.search)

    // communicator variables:
    var chatLayout = document.getElementById('chatForm')
    var genieLayout = document.getElementById('genieForm')

    const chatSendButton = document.getElementById('send');
    const chatInputElement = document.getElementById('input');
    const chatConsoleElement = document.getElementById('chatConsole');

    
    // capturing location API

    function getLocation() {
        if (navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(showPosition, showError, {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
          });
        } else {
          alert("Geolocation is not supported by this browser.");
        }
      }
    
    function showPosition(position) {
        socket.emit('update_location', JSON.stringify({data: position}))
        console.log("Latitude: " + position.coords.latitude +
                    "\nLongitude: " + position.coords.longitude +
                    "\nAccuracy: " + position.coords.accuracy + " meters.");
    }
      
    function showError(error) {
        switch(error.code) {
            case error.PERMISSION_DENIED:
            console.log("User denied the request for Geolocation.");
            // Generate a window for user to enter location
            // consoleElement.innerHTML = '<p>Please enable the location to continue using the application</p>'
            break;
            case error.POSITION_UNAVAILABLE:
            console.log("Location information is unavailable.");
            break;
            case error.TIMEOUT:
            console.log("The request to get user location timed out.");
            break;
            default:
            console.log("An unknown error occurred.");
            break;
        }
    }

    // From communicator page:
    console.log("params from registration page",params.get('DeviceID'))

    var socket = io(
        'https://meet-basilisk-adversely.ngrok-free.app/', {
        query: {
            DeviceID: params.get('DeviceID')
        }
    });

    //Event handlers - Socket
    socket.on('connect', function() {
        console.log('Connected to SocketIO server!');
    });

    socket.on('your_session_id', data => {
        console.log('My session ID is:', data.sid);
        getLocation()
    });

    socket.on('disconnect', function() {
        pc.close();
        console.log('Disconnected from server');
    });

    socket.on('no_peers', function(msg) {
        console.log('No remote peers has been found');
        // wishMessage.value = '';
        // bidValue.value = '';
        consoleElement.innerHTML = `<p>No one found in your area. Customers are actively adapting to the platform. Stay tuned:)</p>`;
    });

    socket.on('refine_request', function(msg) {
        console.log('People found but unable to server your request, can you refine your search?');
        wishMessage.value = '';
        bidValue.value = '';
        consoleElement.innerHTML = `<p>Can you refine your search criteria?</p>`;
    });

    socket.on('oncommunicator', function() {
        chatConsoleElement.innerHTML += `User connected`
    });


    // WebRTC configuration and handlers

    const configuration = {
        sdpSemantics: 'unified-plan',
        iceServers: 
        [
            {
                "url": "stun:global.stun.twilio.com:3478",
                "urls": "stun:global.stun.twilio.com:3478",
            },
            {
                "url": "turn:global.turn.twilio.com:3478?transport=udp",
                "username": "11dcd091f69945cc6594b4db007136722e3c266b610632f1087ca36c6da64dac",
                "urls": "turn:global.turn.twilio.com:3478?transport=udp",
                "credential": "6Z6TPhGWJm6f5eY1o4J7Ms/V6L3XbSklCkGdNk9lnZk=",
            },
            {
                "url": "turn:global.turn.twilio.com:3478?transport=tcp",
                "username": "11dcd091f69945cc6594b4db007136722e3c266b610632f1087ca36c6da64dac",
                "urls": "turn:global.turn.twilio.com:3478?transport=tcp",
                "credential": "6Z6TPhGWJm6f5eY1o4J7Ms/V6L3XbSklCkGdNk9lnZk=",
            },
            {
                "url": "turn:global.turn.twilio.com:443?transport=tcp",
                "username": "11dcd091f69945cc6594b4db007136722e3c266b610632f1087ca36c6da64dac",
                "urls": "turn:global.turn.twilio.com:443?transport=tcp",
                "credential": "6Z6TPhGWJm6f5eY1o4J7Ms/V6L3XbSklCkGdNk9lnZk=",
            }
        ]
    };

    var pc = new RTCPeerConnection(configuration);

    socket.on('message', async function(msg) {
        // console.log('Received message from server:', msg);
        const data = JSON.parse(msg);
        console.log(Date.now(),'Message from signalling server:', data);
        if (data.type === 'offer') {
            console.log("controller for offer", data)
            await handleOfferAndCreateAnswer(data.offer);
        } else if (data.type === 'answer') {
            console.log("controller for answer", data)
            await handleAnswer(data);
        } 
        else if (data.type === 'candidate') {
            console.log("controller for candiate", data)
            pc.addIceCandidate(new RTCIceCandidate(data.candidate));
        }                
    });

    pc.onicecandidate = event => {
            if (event.candidate) {
                console.log('calling ice candidate')
                console.log('candidate Type:', event.candidate.type)
                // waiting for specific time to ensure offers has been broadcasted to all the peers
                // TODO: Make the timing event based once the answer has been received from the peer.
                setTimeout(() => {
                        socket.send(JSON.stringify(
                            {
                                type: 'candidate',
                                candidate: {
                                    candidate: event.candidate.candidate,
                                    sdpMLineIndex: event.candidate.sdpMLineIndex,
                                    sdpMid: event.candidate.sdpMid,
                                    usernameFragment: event.candidate.usernameFragment
                                }
                            }
                        )
                    );
                        // console.log("Message sent after 1 second");
                }, 1000);                  
            }
        };

    pc.onsignalingstatechange = event => {
        console.log("signalling state change event:", event)
    }

    pc.onicegatheringstatechange = event => {
        console.log("ice gathering state change event:", event)
    }

    pc.oniceconnectionstatechange = event => {
        console.log(`ICE Connection State: ${pc.iceConnectionState}`);
        console.log('ICE Connection State change event:', event);
    };

    pc.onicecandidateerror = event => {
        console.error('ICE Candidate Error:', event);
    };
    
    pc.onconnectionstatechange = event => {
        console.log(`connection State change: ${pc.connectionState}`);
        console.log('connection State change event:', event);
        if (pc.connectionState === "failed") {
            console.error("Peer Connection Failed.");
            console.log(pc)
            // refresh the browswer for availabity in fleet once the connection has been dropped.
            window.location.reload()
            // Implement recovery or reconnection strategies here
            // recoverConnection(pc);
        }
    };

    async function handleOfferAndCreateAnswer(offer) {
            try {
                remote_description = new RTCSessionDescription(offer)
                await pc.setRemoteDescription(remote_description);
                const answer = await pc.createAnswer();
                await pc.setLocalDescription(answer);
                console.log('answer created successfully')

                // Send the answer back to the offerer via the signaling server
                socket.send(JSON.stringify({
                    'type': pc.localDescription.type,
                    'sdp': pc.localDescription.sdp
                }));
            } catch (error) {
                console.error('Error handling offer or creating answer:', error);
            }
        }

    async function handleAnswer(answer) {
        try {
            console.log("working on handling answer:", answer)
            const remoteDesc = new RTCSessionDescription({type: 'answer', sdp: answer.sdp});
            await pc.setRemoteDescription(remoteDesc);
            console.log("Remote description set successfully")

        } catch (error) {
            console.error('Error setting remote description from answer:', error);
        }
    }

    pc.ondatachannel = function(event) {
        const channel = event.channel;
        console.log(`Data channel received: ${channel.label}`);

        // Set event handlers for the data channel
        channel.onopen = function() {
            console.log(`Data channel ${channel.label} opened by remote peer.`);
            if (chatLayout.style.display === 'none'){
                genieLayout.style.display = 'none'
                chatLayout.style.display = 'block'
                
            }
            // socket.emit('chat_established', {'data': 'connected'});
            socket.send(JSON.stringify({type: 'dataChannelOpened'})); 
            // chatConsoleElement.innerHTML += `User connected`;           
            // sessionStorage.setItem("channel", JSON.stringify(channel))
            // window.location.href = 'communicator';
        };
        

        channel.onmessage = function(event) {
            // console.log("SDP final state local:", pc.localDescription.sdp);
            // console.log("SDP final state remote:", pc.remoteDescription.sdp);
            // console.log("SDP final state remote:", pc.sdp);
            chatConsoleElement.innerHTML += `<p>Received: ${event.data}</p>`;
            console.log(`Message received on ${channel.label}: ${event.data}`);
        };

        channel.onclose = function() {
            console.log(`Data channel ${channel.label} closed.`);
        };

        chatSendButton.onclick = function() {
            let message = chatInputElement.value;
            channel.send(message);
            chatConsoleElement.innerHTML += `<p>Sent: ${message}</p>`;
            chatInputElement.value = '';
        };
    };            

    broadcastButton.onclick = event =>{
        // ensuring page is not reloaded()
        

        console.log("create offer event data:", event)
        const dataChannel = pc.createDataChannel("chat");
        let broadcastMsg = wishMessage.value;
        pc.createOffer().then(offer => {
            pc.setLocalDescription(offer);
            console.log("Offer function has been activated")
            console.log("wish message value", wishMessage.value)
            console.log(pc)
            // socket.send(JSON.stringify({type: 'offer', offer: offer, wishMessage: 'test'}));
            socket.emit('onbroadcast', JSON.stringify({type: 'offer', offer: offer, wishMessage: broadcastMsg}));
            // document.getElementById('genieForm').reset();

        }).catch(e => console.error(e));

        //Disabling the values on the prompt
        wishMessage.value = '';
        bidValue.value = '';
        consoleElement.innerHTML = '';

        //State change events
        dataChannel.onopen = event => {
            if (chatLayout.style.display === 'none'){
                genieLayout.style.display = 'none'
                chatLayout.style.display = 'block'
                
            }
            socket.send(JSON.stringify({type: 'dataChannelOpened'}));
            // chatConsoleElement.innerHTML += `User connected`;
            // console.log("object value is:", dataChannel)
            // sessionStorage.setItem("channel", JSON.stringify(dataChannel))
            // window.location.href = 'communicator';
        }
        dataChannel.onmessage = function (event) {
            // outputElement.innerHTML += '<p>From remote server:' event.data '</p>';
            // console.log("SDP final state local:", pc.localDescription.sdp);
            // console.log("SDP final state remote:", pc.remoteDescription.sdp);
            chatConsoleElement.innerHTML += `<p>Received: ${event.data}</p>`;
            console.log("Message from client:", event.data);
        };    
        
        chatSendButton.onclick = event => {
            let message = chatInputElement.value;
            dataChannel.send(message);
            chatConsoleElement.innerHTML += `<p>Sent: ${message}</p>`;
            chatInputElement.value = '';
        };
        
        //Log console message as an event within the data
        
        console.log("message from zenie", wishMessage.value, bidValue.value)
    }
});