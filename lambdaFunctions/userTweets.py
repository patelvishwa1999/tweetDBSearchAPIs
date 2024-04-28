import json
import boto3
import logging
from collections import OrderedDict
from datetime import datetime, timedelta


# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')

# Initialize logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class LRUCache:
    def __init__(self, capacity: int, ttl=timedelta(minutes=5)):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.ttl = ttl  # Time-to-live for cache entries

    def get(self, key):
        item = self.cache.get(key, None)
        if item and datetime.now() - item['timestamp'] < self.ttl:
            self.cache.move_to_end(key)  # Mark as recently used
            return item['data']
        if item:
            del self.cache[key]  # Remove expired item
        return None

    def put(self, key, value):
        self.cache[key] = {'data': value, 'timestamp': datetime.now()}
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # Remove least recently used item

    def save_to_s3(self, bucket_name, object_key):
        # Serialize only the data part of the cache for S3 storage
        serialized_cache = json.dumps({k: {'data': v['data'], 'timestamp': v['timestamp'].isoformat()} for k, v in self.cache.items()}, default=str)
        s3 = boto3.client('s3')
        s3.put_object(Bucket=bucket_name, Key=object_key, Body=serialized_cache)

    def load_from_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        try:
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            loaded_cache = json.loads(response['Body'].read())
            self.cache = OrderedDict({k: {'data': v['data'], 'timestamp': datetime.fromisoformat(v['timestamp'])} for k, v in loaded_cache.items()})
        except Exception as e:
            print("Error loading cache from S3:", e)
            self.cache = OrderedDict()  # Start with an empty cache if there's an error

# Initialize cache
cache = LRUCache(capacity=10)

def lambda_handler(event, context):
    try:
        user_id = event['queryStringParameters']['user_id']
        cache_key = f"tweets_{user_id}"
        cache.load_from_s3('cachebucketaws', 'userTweets')

        # Check cache first
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            logger.info("Returning cached data.")
            return {
                'statusCode': 200,
                'body': json.dumps(cached_response),
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
            }

        # Query DynamoDB if not in cache
        logger.info(f"Querying tweets for user_id: {user_id}")
        response = dynamodb.query(
            TableName='tweets',
            IndexName='user_id-index',
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': {'N': str(user_id)}}
        )
        items = response.get('Items', [])
        logger.info(f"Found {len(items)} tweets for user_id: {user_id}")

        # Update cache and save to S3
        cache.put(cache_key, items)
        cache.save_to_s3('cachebucketaws', 'userTweets')

        return {
            'statusCode': 200,
            'body': json.dumps(items),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }
        
    except KeyError as ke:
        logger.error("Missing user_id parameter")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing user_id parameter'}),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error'}),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }

