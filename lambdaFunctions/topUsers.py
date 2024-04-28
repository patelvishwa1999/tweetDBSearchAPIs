import json
import psycopg2
import boto3
import collections
import pickle
import os
from datetime import datetime, timedelta

class LRUCache:
    def __init__(self, capacity: int, ttl=timedelta(minutes=5)):
        self.cache = collections.OrderedDict()
        self.capacity = capacity
        self.ttl = ttl

    def get(self, key):
        item = self.cache.get(key)
        if item and (datetime.now() - item['timestamp']) < self.ttl:
            self.cache.move_to_end(key)
            return item['data']
        elif item:
            self.cache.pop(key)  # Remove expired item
        return None

    def put(self, key, value):
        self.cache[key] = {'data': value, 'timestamp': datetime.now()}
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def save_to_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        serialized_cache = json.dumps({k: {'data': v['data'], 'timestamp': v['timestamp'].isoformat()} for k, v in self.cache.items()}, default=str)
        s3.put_object(Bucket=bucket_name, Key=object_key, Body=serialized_cache)

    def load_from_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        try:
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            loaded_cache = json.loads(response['Body'].read())
            self.cache = collections.OrderedDict({k: {'data': v['data'], 'timestamp': datetime.fromisoformat(v['timestamp'])} for k, v in loaded_cache.items()})
        except Exception as e:
            self.cache = collections.OrderedDict()

def lambda_handler(event, context):
    option = event['queryStringParameters']['option']
    limit = event['queryStringParameters']['numberOfUsers']
    cache_key = f"{option}_{limit}"

    cache = LRUCache(capacity=10)
    cache.load_from_s3('cachebucketaws', 'top10users')

    # Try to retrieve the response from cache
    response = cache.get(cache_key)
    if response is None:
        # Connect to PostgreSQL database
        conn = psycopg2.connect(
            host = 'YOUR_RDS_HOST',
            user = 'YOUR_USERNAME',
            password = 'YOUR_PASSWORD',
            database = 'postgres',
            port = 5432
        )
        cursor = conn.cursor()

        # Execute SQL query to fetch data
        query = f"SELECT name, screen_name, {option} FROM users ORDER BY {option} DESC LIMIT {limit};"
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        response = [dict(zip(columns, row)) for row in rows]

        # Update cache
        cache.put(cache_key, response)
        cache.save_to_s3('cachebucketaws', 'top10users')

        # Close cursor and connection
        cursor.close()
        conn.close()

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(response)
    }
