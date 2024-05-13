from pymongo import MongoClient
from pymongo.collection import Collection
from datetime import datetime, timedelta
import os

# Replace 'localhost' with your MongoDB host if different
# client = MongoClient('mongodb://localhost:27017/')
mongo_uri = os.getenv('MONGO_URI', 'mongodb://tvast:password@127.0.0.1:27017/ps?authSource=admin')
client = MongoClient(mongo_uri)
db = client.DeviceTracking

def get_device_collection() -> Collection:
    return db.devices

def get_location_collection() -> Collection:
    return db.locations

def get_active_user_endpoints() -> list:
    """Retrieve a list of active user endpoints from the locations collection."""
    # We assume 'active' might mean having a recent timestamp, modify as needed
    recent_time_limit = datetime.now() - timedelta(hours=1)
    print(recent_time_limit)
    active_users = get_location_collection().find({
        'Timestamp': {'$gte': recent_time_limit}
    }, {
        'Endpoint': 1, '_id': 0
    })
    print(active_users)
    return [user['Endpoint'] for user in active_users if 'Endpoint' in user]