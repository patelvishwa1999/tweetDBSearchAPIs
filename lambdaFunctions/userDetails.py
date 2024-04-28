import json
import boto3
import psycopg2
from collections import OrderedDict
import time

class LRUCache:
    def __init__(self, capacity: int, ttl: int):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.ttl = ttl  # Time to live in seconds

    def get(self, key):
        item = self.cache.get(key, None)
        if item and (time.time() - item['time']) < self.ttl:
            self.cache.move_to_end(key)
            return item['data']
        if item:
            self.cache.pop(key)  # Remove stale data
        return None

    def put(self, key, data):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = {'data': data, 'time': time.time()}
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def save_to_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        # Serialize only the data and time for each cache item
        serialized_cache = json.dumps({key: {'data': val['data'], 'time': val['time']} for key, val in self.cache.items()}, default=str)
        s3.put_object(Bucket=bucket_name, Key=object_key, Body=serialized_cache)

    def load_from_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        try:
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            loaded_data = json.loads(response['Body'].read())
            # Ensure that we maintain the order and structure of the cache
            self.cache = OrderedDict((k, {'data': v['data'], 'time': v['time']}) for k, v in loaded_data.items())
        except Exception:
            self.cache = OrderedDict()

# Instantiate the cache with a capacity for 10 items and a TTL of 300 seconds (5 minutes)
cache = LRUCache(capacity=10, ttl=300)

def lambda_handler(event, context):
    uid_str = event['queryStringParameters']['user_id']
    cache.load_from_s3('cachebucketaws', 'userDetails')

    cached_user = cache.get(uid_str)
    if cached_user:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(cached_user)
        }

    try:
        uid = int(uid_str)
    except ValueError:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid user_id, must be an integer'}),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }

    # Connect to PostgreSQL database
    conn = psycopg2.connect(
        host = 'YOUR_RDS_HOST',
        user = 'YOUR_USERNAME',
        password = 'YOUR_PASSWORD',
        database = 'postgres',
        port = 5432
    )
    cursor = conn.cursor()

    # Execute SQL query
    cursor.execute(f"SELECT name, description, screen_name, verified, followers_count, friends_count, statuses_count FROM users WHERE user_id = {uid};")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    response = [dict(zip(columns, row)) for row in rows]

    cache.put(uid_str, response)
    cache.save_to_s3('cachebucketaws', 'userDetails')

    cursor.close()
    conn.close()

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(response)
    }

