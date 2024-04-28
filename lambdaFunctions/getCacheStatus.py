import json
import boto3

def lambda_handler(event, context):
    # Define S3 bucket and object key
    bucket_name = 'cachebucketaws'
    object_key = event['queryStringParameters']['key']

    # Initialize S3 client
    s3 = boto3.client('s3')

    try:
        # Retrieve data from S3
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        data = json.loads(response['Body'].read())

        # Extract keys with non-empty data
        keys_with_data = [key for key, value in data.items() if value]

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(keys_with_data)
        }
    except Exception as e:
        # Handle error if S3 retrieval fails
        print(f"Error reading cache from S3: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Internal Server Error'})
        }
