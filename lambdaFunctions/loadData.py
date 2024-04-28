
import json
import boto3
import psycopg2
import datetime
from botocore.exceptions import ClientError

class DynamoDBHandler:
    """Encapsulates an Amazon DynamoDB table for tweets, hashtags, and retweets."""
    
    def __init__(self, dyn_resource, table_name):
        """
        :param dyn_resource: A Boto3 DynamoDB resource.
        :param table_name: Name of the DynamoDB table.
        """
        self.dyn_resource = dyn_resource
        self.table = self.dyn_resource.Table(table_name)

    def write_batch(self, items):
        """
        Fills the DynamoDB table with the specified data using batch_writer().

        :param items: The data to put in the table.
        """
        try:
            with self.table.batch_writer() as writer:
                for item in items:
                    writer.put_item(Item=item)
        except ClientError as err:
            print(
                f"Error writing batch to table {self.table.name}: {err.response['Error']['Code']}: {err.response['Error']['Message']}"
            )
            raise

# Initialize set to keep track of processed tweet IDs to avoid duplicates
seen_tweets = set()
seen_users = set()

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')

# Initialize S3 client
s3 = boto3.client('s3')

host = 'YOUR_RDS_HOST'
user = 'YOUR_USERNAME'
password = 'YOUR_PASSWORD'
database = 'postgres'
port = 5432

# Specify the table names               
tweets_table_name = 'tweets'
hashtags_table_name = 'hashtags'
retweets_table_name = 'retweets'

# Connect to PostgreSQL RDS
conn = psycopg2.connect(
    host=host,
    port=port,
    database=database,
    user=user,
    password=password
)
cursor = conn.cursor()

# Initialize DynamoDB tables handler
tweets_table_handler = DynamoDBHandler(dynamodb, tweets_table_name)
hashtags_table_handler = DynamoDBHandler(dynamodb, hashtags_table_name)
retweets_table_handler = DynamoDBHandler(dynamodb, retweets_table_name)

def process_records(records, start_line):
    """
    Processes a chunk of records starting from the specified line number.

    :param records: List of records (lines) to process.
    :param start_line: Line number to start processing from.
    """
    counter = 0 
    tweet_batch = []
    hashtag_batch = []
    retweet_batch = []
    try:
        for record in records:
            try:
                if record:
                    tweet_data = json.loads(record.strip())
                    tweet_id = tweet_data["id"]
                    counter += 1
                    print(f"Iteration no // : {counter}s processed")
                    
                    # Check if tweet ID is already processed
                    if tweet_id in seen_tweets:
                        continue
                    
                    # Prepare tweet item
                    tweet_item = {
                        'tweet_id': str(tweet_id),
                        'text': tweet_data.get('text', ''),
                        'created_at': tweet_data.get('created_at', ''),
                        'retweet_count': tweet_data.get('retweet_count', 0),
                        'favorite_count': tweet_data.get('favorite_count', 0),
                        'user_id': tweet_data.get('user', {}).get('id', ''),
                        'language': tweet_data.get('lang', ''),
                        'quote_count': tweet_data.get('quote_count', 0),
                        'reply_count': tweet_data.get('reply_count', 0),
                        'tweet_type': 'retweet' if tweet_data['text'].startswith('RT') else 'tweet'
                    }
                    if tweet_item not in tweet_batch:
                        tweet_batch.append(tweet_item)
                    seen_tweets.add(tweet_id)  # Add tweet ID to seen_tweets
                    
                    # Prepare hashtag items
                    entities = tweet_data.get('entities', {})
                    hashtags = entities.get('hashtags', [])
                    for hashtag in hashtags:
                        hashtag_text = hashtag.get('text', '')
                        if hashtag_text:
                            hashtag_item = {
                                'hashtag_text': hashtag_text,
                                'tweet_id': str(tweet_id)
                            }
                            if hashtag_item not in hashtag_batch:
                                hashtag_batch.append(hashtag_item)
                    
                    # Prepare retweet items
                    retweeted_status = tweet_data.get('retweeted_status')
                    if retweeted_status:
                        retweet_id = retweeted_status.get('id', '')
                        if retweet_id and retweet_id not in seen_tweets:  # Check for duplicates
                            retweet_item = {
                                'retweet_id': str(retweet_id),
                                'parent_tweet_id': str(tweet_id),
                                'retweet_text': retweeted_status.get('text', ''),
                                'retweet_user_id': retweeted_status.get('user', {}).get('id', ''),
                                'parent_user_id': tweet_data.get('user', {}).get('id', ''),
                                'retweet_created_at': retweeted_status.get('created_at', '')
                            }
                            if retweet_item not in retweet_batch:
                                retweet_batch.append(retweet_item)
                            seen_tweets.add(retweet_id)  # Add retweet ID to seen_tweets
                            
                    # If batch size is 25 or no more records, write the batches
                    if len(tweet_batch) >= 25 or counter == len(records):
                        tweets_table_handler.write_batch(tweet_batch)
                        tweet_batch.clear()  # Clear the batch
                    if len(hashtag_batch) >= 25 or counter == len(records):
                        hashtags_table_handler.write_batch(hashtag_batch)
                        hashtag_batch.clear()  # Clear the batch
                    if len(retweet_batch) >= 25 or counter == len(records):
                        retweets_table_handler.write_batch(retweet_batch)
                        retweet_batch.clear()  # Clear the batch
                        
                    # Insert user into PostgreSQL RDS
                    user_data = tweet_data["user"]
                    user_id = user_data.get("id")
                    if user_id not in seen_users:
                        try:
                            insert_user_query = """
                            INSERT INTO users (user_id, name, screen_name, user_created_at, verified, description, location, followers_count, friends_count, listed_count, favourites_count, statuses_count)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (user_id) DO NOTHING;
                            """
                            cursor.execute(insert_user_query, (
                                user_id,
                                user_data.get('name', ''),
                                user_data.get('screen_name', ''),
                                datetime.datetime.strptime(user_data.get('created_at', ''), '%a %b %d %H:%M:%S %z %Y'),
                                user_data.get('verified', False),
                                user_data.get('description', ''),
                                user_data.get('location', ''),
                                user_data.get('followers_count', 0),
                                user_data.get('friends_count', 0),
                                user_data.get('listed_count', 0),
                                user_data.get('favourites_count', 0),
                                user_data.get('statuses_count', 0)
                            ))
                            conn.commit()
                            seen_users.add(user_id)
                        except Exception as e:
                            conn.rollback()
                            print("Error inserting user:", e)
                    
            except Exception as e:
                print("Error processing record:", e)
                continue  # Continue to the next record
            
    except Exception as e:
                print("Error processing records:", e)


# Lambda function handler
def lambda_handler(event, context):
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']
    
    # Read file from S3
    response = s3.get_object(Bucket=bucket_name, Key=file_key)
    content = response['Body'].read().decode('utf-8')
    records = content.split('\n')
    print(f"Length:{len(records)}")
    
    # Process records
    process_records(records, 0)  # Start processing from line 0
    
    print("Finished loading Users data. Total unique Users processed:", len(seen_users))
    print("Finished loading Tweets data. Total unique tweets/retweets processed:", len(seen_tweets))
    
    # Close database connection
    cursor.close()
    conn.close()

    return {
        'statusCode': 200,
        'body': json.dumps('Data Loading completed successfully')
    }
