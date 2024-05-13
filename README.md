# zentica
Changes the way to connect with people

**Folder Structure**:
```
├── Dockerfile
├── LICENSE
├── README.md
├── app.py
├── db.py
├── docker-compose.yml
├── requirements.txt
└── static
    ├── css
    │   ├── geniestyle.css
    │   └── styles.css
    ├── genie.html
    ├── js
    │   ├── genie-script.js
    │   └── script.js
    └── registration.html
```

**Environment Setup:**

* Tools required:
    * Docker(https://www.docker.com/get-started/)


* Prerequisite:
    - Create a `.env` file in the root folder with the below format
    ```
    API_KEY=XXXXXXXXXXXXXXXXXXX
    ```
    - Obtain all the necessary API keys supporting the application and configure within the `.env` file
* Build:
    * Run `docker compose up` in the terminal.