
import json
import boto3
from decimal import Decimal
from datetime import datetime, timezone
import traceback

### Input dates must be in the format: '%a %b %d %H:%M:%S %z %Y' (ex: "Sat Apr 25 14:25:38 +0000 2020")

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError

def lambda_handler(event, context):
    # Extract search string and time range from the event
    search_string = event['queryStringParameters']['search_string']
    after = event['queryStringParameters'].get('after', None) # format: '%a %b %d %H:%M:%S %z %Y'
    before = event['queryStringParameters'].get('before', None) # format: '%a %b %d %H:%M:%S %z %Y'
    
    if before == None:
        before = datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
    
    if after == None:
        after = datetime(1, 1, 1, tzinfo=timezone.utc)

    # Initialize response list
    tweets = []

    try:
        # Scan the tweets table for items where the text field contains the search string
        tweets_table = dynamodb.Table('tweets')

        # Build the filter expression and expression attribute values
        filter_expression = 'contains(#txt, :search)'
        expression_attribute_names = {'#txt': 'text'}
        expression_attribute_values = {':search': search_string}

        response = tweets_table.scan(
            FilterExpression=filter_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )

        # Extract the items from the response
        items = response['Items']
        
        # Filter tweets based on the time range
        filtered_items = []
        for item in items:
            tweet_timestamp = datetime.strptime(item["created_at"], "%a %b %d %H:%M:%S %z %Y")
            if after != datetime(1, 1, 1, tzinfo=timezone.utc):
                after_timestamp = datetime.strptime(after, "%a %b %d %H:%M:%S %z %Y")
            else: after_timestamp = after
            if before != datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc):
                before_timestamp = datetime.strptime(before, "%a %b %d %H:%M:%S %z %Y")
            else: before_timestamp = before
            
            if tweet_timestamp < after_timestamp:
                continue
            
            if tweet_timestamp > before_timestamp:
                continue
            
            filtered_items.append(item)
        
        # Convert Decimal types to standard Python types
        for item in filtered_items:
            for key, value in item.items():
                if isinstance(value, Decimal):
                    item[key] = int(value)
        
        # Return the list of tweets as JSON object
        return {
            'statusCode': 200,
            'body': json.dumps(filtered_items, default=str)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }