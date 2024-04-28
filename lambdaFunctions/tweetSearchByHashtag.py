import json
import boto3
import logging
from collections import OrderedDict
import time

class LRUCache:
    def __init__(self, capacity: int, ttl: int):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.ttl = ttl  # Time-to-live in seconds

    def get(self, key):
        if key in self.cache and (time.time() - self.cache[key]['time']) < self.ttl:
            self.cache.move_to_end(key)
            return self.cache[key]['data']
        elif key in self.cache:
            # If the item is expired, remove it from the cache.
            self.cache.pop(key)
        return None

    def put(self, key, value):
        # Store the value along with the current timestamp.
        self.cache[key] = {'data': value, 'time': time.time()}
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def save_to_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        # Serialize the cache including timestamps to ensure it can be fully restored.
        serialized_cache = json.dumps({k: {'data': v['data'], 'time': v['time']} for k, v in self.cache.items()}, default=str)
        s3.put_object(Bucket=bucket_name, Key=object_key, Body=serialized_cache)

    def load_from_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        try:
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            loaded_cache = json.loads(response['Body'].read())
            # Properly reconstruct the cache from the loaded data
            self.cache = OrderedDict({k: {'data': v['data'], 'time': v['time']} for k, v in loaded_cache.items()})
        except Exception as e:
            logging.error(f"Failed to load cache from S3: {str(e)}")
            self.cache = OrderedDict()  # Reset cache if there's an error

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')

# Initialize cache with TTL of 300 seconds (5 minutes)
cache = LRUCache(capacity=10, ttl=300)

def lambda_handler(event, context):
    search_string = event['queryStringParameters']['search_string']
    cache_key = f"hashtags_{search_string}"
    cache.load_from_s3('cachebucketaws', 'tweetSearchByHashtag')

    cached_response = cache.get(cache_key)
    if cached_response is not None:
        logger.info("Returning cached data.")
        return {
            'statusCode': 200,
            'body': json.dumps(cached_response),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }

    logger.info(f"Querying hashtags for search_string: {search_string}")
    response = dynamodb.query(
        TableName='hashtags',
        IndexName='hashtag_text-index',
        KeyConditionExpression='hashtag_text = :search_string',
        ExpressionAttributeValues={':search_string': {'S': search_string}}
    )
    tweet_ids = [item['tweet_id']['S'] for item in response['Items']]
    
    cache.put(cache_key, tweet_ids)
    cache.save_to_s3('cachebucketaws', 'tweetSearchByHashtag')

    return {
        'statusCode': 200,
        'body': json.dumps(tweet_ids),
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
    }

