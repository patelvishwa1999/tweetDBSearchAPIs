import json
import boto3
import logging
from collections import OrderedDict
from datetime import datetime, timedelta

class LRUCache:
    def __init__(self, capacity: int, ttl: timedelta):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.ttl = ttl

    def get(self, key):
        item = self.cache.get(key, None)
        if item and datetime.now() < item['expiry']:
            self.cache.move_to_end(key)
            return item['data']
        elif item:
            del self.cache[key]  # Remove expired item
        return None

    def put(self, key, value):
        expiry = datetime.now() + self.ttl
        item = {'data': value, 'expiry': expiry}
        if key in self.cache:
            self.cache.move_to_end(key)
        elif len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)
        self.cache[key] = item

    def save_to_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        serialized_cache = json.dumps({k: {'data': v['data'], 'expiry': v['expiry'].isoformat()} for k, v in self.cache.items()}, default=str)
        s3.put_object(Bucket=bucket_name, Key=object_key, Body=serialized_cache)

    def load_from_s3(self, bucket_name, object_key):
        s3 = boto3.client('s3')
        try:
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            loaded_cache = json.loads(response['Body'].read())
            self.cache = OrderedDict({k: {'data': v['data'], 'expiry': datetime.fromisoformat(v['expiry'])} for k, v in loaded_cache.items()})
        except s3.exceptions.NoSuchKey:
            print("Cache not found in S3, starting a new one.")
        except Exception as e:
            print(f"Error loading cache: {str(e)}")

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb')

# Initialize logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize cache with 5-minute TTL
cache = LRUCache(capacity=10, ttl=timedelta(minutes=5))

def lambda_handler(event, context):
    try:
        parent_tweet_id = event['queryStringParameters']['parent_tweet_id']
        cache_key = f"retweets_{parent_tweet_id}"
        cache.load_from_s3('cachebucketaws', 'tweetRetweets')

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
        logger.info(f"Querying retweets for parent_tweet_id: {parent_tweet_id}")
        response = dynamodb.query(
            TableName='retweets',
            IndexName='parent_tweet_id-index',
            KeyConditionExpression='parent_tweet_id = :pid',
            ExpressionAttributeValues={':pid': {'S': parent_tweet_id}}
        )
        items = response.get('Items', [])
        logger.info(f"Found {len(items)} retweets for parent_tweet_id: {parent_tweet_id}")

        # Update cache and save to S3
        cache.put(cache_key, items)
        cache.save_to_s3('cachebucketaws', 'tweetRetweets')

        return {
            'statusCode': 200,
            'body': json.dumps(items),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }
        
    except KeyError as ke:
        logger.error("Missing parent_tweet_id parameter")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Missing parent_tweet_id parameter'}),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error'}),
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}
        }
