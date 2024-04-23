#running venv using conda
# /usr/local/Caskroom/miniforge/base/envs/zentica/bin/python3 app.py

# hypercorn <file_name>:<ASGIInstance> --reload
hypercorn app:zentica_demo --reload


# starting web service
ngrok start demozentica





