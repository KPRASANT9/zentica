document.getElementById('registrationForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent the default form submission

    const username = document.getElementById('username').value;
    const location = document.getElementById('location').value;
    const profile = document.getElementById('profile').value;

    console.log('Registering:', username, location, profile);

    // Post request to load the User information.
    fetch('http://localhost:8000/api/device/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({"DeviceID": username, "Location": location, "Profile": profile})
    })
    .then(response => response.json())
    .then(
        data => {
            console.log('Success:', data)
            if (data.status == 'success') {
                const url = `client.html?DeviceID=${encodeURIComponent(username)}`;
                window.location.href = url; //navigate to client.html
            } else {
                alert("Issue with the registration!")
            }          
        }       
    )
    .catch(error => console.error('Error:', error));


    // Simulate sending data to a server for GET request

    // function buildUrl(baseUrl, params) {
    //     const query = new URLSearchParams(params);
    //     return `${baseUrl}?${query.toString()}`;
    // }

    // function fetchData(baseUrl, params) {
    //     // Build the URL with parameters
    //     const url = buildUrl(baseUrl, params);
    
    //     // Use fetch to send the GET request
    //     fetch(url)
    //         .then(response => {
    //             if (!response.ok) {
    //                 throw new Error('Network response was not ok ' + response.statusText);
    //             }
    //             return response.json(); // Parse JSON data from the response
    //         })
    //         .then(data => {
    //             console.log('Success:', data); // Handle the data received from the server
    //         })
    //         .catch(error => {
    //             console.error('Error:', error); // Handle any errors
    //         });
    // }
    
    // // Example usage
    // const baseUrl = 'http://localhost:8000/api/device/track';
    // const params = {
    //     DeviceID: 127,
    // };
    // fetchData(baseUrl, params);
    

    // Navigate to the Next Page based on the value.
    

    // Clear form fields after submission
    document.getElementById('registrationForm').reset();
});