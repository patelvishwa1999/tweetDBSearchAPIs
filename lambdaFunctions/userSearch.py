import json
import boto3
import psycopg2
from collections import OrderedDict
import time

class LRUCache:
    def __init__(self, capacity: int, ttl: int):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.ttl = ttl  # TTL in seconds

    def get(self, key):
        key = key.lower()  # Normalize key to lowercase
        item = self.cache.get(key, None)
        if item and (time.time() - item['timestamp'] < self.ttl):
            self.cache.move_to_end(key)
            return item['data']
        if item:
            self.cache.pop(key)  # Remove stale data
        return None

    def put(self, key, data):
        key = key.lower()  # Normalize key to lowercase
        self.cache[key] = {'data': data, 'timestamp': time.time()}
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def save_to_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        # Serialize the cache, ensuring all keys are lowercased
        serialized_cache = json.dumps({k.lower(): v for k, v in self.cache.items()}, default=str)
        s3.put_object(Bucket=bucket_name, Key=object_key, Body=serialized_cache)

    def load_from_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        try:
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            loaded_data = json.loads(response['Body'].read())
            # Load cache and ensure keys are lowercased
            self.cache = OrderedDict((k.lower(), {'data': v['data'], 'timestamp': v['timestamp']}) for k, v in loaded_data.items())
        except Exception as e:
            print(f"Error loading cache: {str(e)}")
            self.cache = OrderedDict()

# Initialize cache with TTL of 300 seconds (5 minutes)
cache = LRUCache(capacity=10, ttl=300)

def lambda_handler(event, context):
    search_string = event['queryStringParameters']['search_string'].lower()  # Convert search string to lowercase
    cache_key = f"{search_string}"
    cache.load_from_s3('cachebucketaws', 'userSearch')

    cached_response = cache.get(cache_key)
    if cached_response:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(cached_response)
        }

    # Set up database connection
    conn = psycopg2.connect(
        host = 'YOUR_RDS_HOST',
        user = 'YOUR_USERNAME',
        password = 'YOUR_PASSWORD',
        database = 'postgres',
        port = 5432
    )
    cursor = conn.cursor()

    query = f"""
        SELECT user_id_str, name, description, screen_name, verified, followers_count, friends_count, statuses_count
        FROM users
        WHERE lower(name) LIKE '%{search_string}%' OR lower(screen_name) LIKE '%{search_string}%';
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    columns = [desc[0] for desc in cursor.description]
    response = [dict(zip(columns, row)) for row in rows]

    cache.put(cache_key, response)
    cache.save_to_s3('cachebucketaws', 'userSearch')

    cursor.close()
    conn.close()

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(response)
    }
