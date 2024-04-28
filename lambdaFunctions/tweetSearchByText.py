import json
import boto3
import logging
import time
from collections import OrderedDict
# from utils.cache import LRUCache

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO) 

class LRUCache:
    def __init__(self, capacity: int, ttl: int):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.ttl = ttl  # TTL in seconds

    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if (time.time() - timestamp) < self.ttl:
                self.cache.move_to_end(key)
                return value
            else:
                # Entry has expired, remove it
                self.cache.pop(key)
        return None

    def put(self, key, value):
        current_time = time.time()
        self.cache[key] = (value, current_time)
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def save_to_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        # Serialize only the values and not the timestamps
        serialized_cache = json.dumps({k: v[0] for k, v in self.cache.items()}, default=str)
        s3.put_object(Bucket=bucket_name, Key=object_key, Body=serialized_cache)

    def load_from_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        try:
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            items = json.loads(response['Body'].read())
            # Reload items with current timestamp to reset TTL
            current_time = time.time()
            self.cache = OrderedDict((k, (v, current_time)) for k, v in items.items())
        except s3.exceptions.NoSuchKey:
            print("Cache not found in S3, starting a new one.")

# Initialize cache with capacity and TTL
cache = LRUCache(capacity=10, ttl=300)  # TTL set to 300 seconds (5 minutes)

def lambda_handler(event, context):
    search_string = event['queryStringParameters']['search_string']
    cache_key = f"hashtags_{search_string}"
    cache.load_from_s3('cachebucketaws', 'tweetSearchByText')

    # Check cache first
    cached_response = cache.get(cache_key)
    if cached_response is not None:
        logger.info("Returning cached data.")
        return {
            'statusCode': 200,
            'body': json.dumps(cached_response),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }

    # If not in cache, query DynamoDB
    logger.info(f"Querying hashtags for search_string: {search_string}")
    response = dynamodb.query(
        TableName='hashtags',
        IndexName='hashtag_text-index',
        KeyConditionExpression='hashtag_text = :search_string',
        ExpressionAttributeValues={':search_string': {'S': search_string}}
    )
    tweet_ids = [item['tweet_id']['S'] for item in response['Items']]
    
    # Update cache and save to S3
    cache.put(cache_key, tweet_ids)
    cache.save_to_s3('cachebucketaws', 'tweetSearchByText')

    return {
        'statusCode': 200,
        'body': json.dumps(tweet_ids),
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
    }
