import json
import boto3
import time
from collections import OrderedDict
import decimal
# from utils.cache import LRUCache

class LRUCache:
    def __init__(self, capacity: int, ttl: int):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.ttl = ttl  # Time to live in seconds

    def get(self, key):
        if key in self.cache and (time.time() - self.cache[key]['time']) < self.ttl:
            self.cache[key]['time'] = time.time()
            self.cache.move_to_end(key)
            return self.cache[key]['value']
        elif key in self.cache:
            self.cache.pop(key)  # Remove stale data
        return None

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = {'value': value, 'time': time.time()}
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def save_to_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        serialized_cache = json.dumps(self.cache, default=str)
        s3.put_object(Bucket=bucket_name, Key=object_key, Body=serialized_cache)

    def load_from_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        try:
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            loaded_cache = json.loads(response['Body'].read())
            self.cache = OrderedDict({k: {'value': v['value'], 'time': v['time']} for k, v in loaded_cache.items()})
        except Exception:
            self.cache = OrderedDict()

# Instantiate the cache with a capacity for 10 items and a TTL of 300 seconds (5 minutes)
cache = LRUCache(capacity=10, ttl=300)

def decimal_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    tweet_id = event['queryStringParameters']['tweet_id']
    cache.load_from_s3('cachebucketaws', 'tweetDetails')

    # Check if the data is in cache
    cached_tweet = cache.get(tweet_id)
    if cached_tweet:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(cached_tweet, default=decimal_default)
        }

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('tweets')

    try:
        response = table.get_item(Key={'tweet_id': tweet_id})
        if 'Item' in response:
            item = response['Item']
            cache.put(tweet_id, item)  # Update cache
            cache.save_to_s3('cachebucketaws', 'tweetDetails')  # Save cache to S3

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps(item, default=decimal_default)
            }
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Tweet not found'})
            }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': str(e)})
        }
