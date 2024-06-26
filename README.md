# tweetDBSearchAPIs 

LIVE APPLICATION : `https://adbms.s3.amazonaws.com/home.html`

Search application for a tweet store, combining relational and non-relational datastores to offer various search options and drill-down features for optimized querying of tweet data.

This project implements a caching system and search application for a tweet store using AWS services, Python, and web technologies.

## Architecture :

### Data Models

<img src='https://github.com/patelvishwa1999/tweetDBSearchAPIs/blob/d215e3973eb66dd4857fbfdf94bf5f2a4ad5f13a/docs/model_ADBMS.jpeg' >

### AWS Services Used

*AWS S3 (Simple Storage Service)*: Stores raw data files.

*AWS Lambda* : Parses and routes data to Amazon RDS for relational data and Amazon DynamoDB for non-relational data.

*Amazon RDS (Relational Database Service)*: Stores user data.

*Amazon DynamoDB*: Stores tweet data in three tables - one for tweets, one for retweets and one for hashtags.

*Amazon API Gateway*: To build REST APIs on top of lambda functions of query.

<img src='https://github.com/patelvishwa1999/tweetDBSearchAPIs/blob/d215e3973eb66dd4857fbfdf94bf5f2a4ad5f13a/docs/system_architecture_ADBMS.jpeg' >


## Search APIs:

`userSearch` API: Queries the users table indexed on name and screen_name.

`tweetSearchByHashtag` API: Accesses the hashtags table using hashtag_text as a partition key to get tweet_ids.

`tweetSearchByText` API: Scans the tweets table to get tweets containing a string.

`tweetSearchByTextAndTime` API: Scans the tweets table to get tweets containing a string in a time range.

`userDetails` API: Fetches details from the users table indexed on user_id.

`tweetDetails` API: Retrieves tweet details from the tweets table indexed on tweet_id.

`userTweets` API: Pulls tweets from the user_id-index index of tweets table with user_id partition key.

`tweetRetweets` API: Accesses the parent_tweet_id-index of retweets table with parent_tweet_id partition key.

`topUsers` API: Ranks users by querying the users table indexed on dynamic user attributes like follower_count or favourites_count or friends_count.

`getCacheStatus` API: get information on current cache keys present. 


## endpoints 
**`userSearch`**

GET | `https://w8yh8w1fxb.execute-api.us-east-1.amazonaws.com/dev/userSearch`

parameter : search_string (String | Required)

response : JSON object of user records

**`tweetSearchByHashtag`**

GET | `https://78ijradnuk.execute-api.us-east-1.amazonaws.com/dev/tweetSearchByHashtag`

parameter : search_string (String | Required)

response : JSON object of tweet_ids

**`userDetails`**

GET | `https://0vtnxfzzsh.execute-api.us-east-1.amazonaws.com/dev/userDetails`

parameter : user_id (String | Required)

response : JSON object of a user detail

**`tweetDetails`**

GET | `https://pltpf3le6d.execute-api.us-east-1.amazonaws.com/dev/tweetDetails`

parameter : tweet_id (String | Required)

response : JSON object of a tweet detail

**`userTweets`**

GET | `https://h8q6rd39sj.execute-api.us-east-1.amazonaws.com/dev/usertweets`

parameter : user_id (String | Required)

response : JSON object of a tweets

**`tweetRetweets`**

GET | `https://2qcgsfyoag.execute-api.us-east-1.amazonaws.com/dev/retweets`

parameter : tweet_id (String | Required)

response : JSON object of a retweets

**`getCacheStatus`**

GET | `https://ys0s790fhg.execute-api.us-east-1.amazonaws.com/dev/getCacheStatus`

parameter : key (Name of the cache) (String | Required)

response : JSON object of present keys in that cache.

**`topUsers`**

GET | `https://yequtjtjbb.execute-api.us-east-1.amazonaws.com/dev/top10users`

parameters : 

 option : followers_count \ friends_count \ favourites_count  (String | Required)
 
 numberOfUsers : number of users to be fetched (Number | Required)

response : JSON object of users.




## Cache Mechanism
### Caching with LRUCache and AWS S3:

#### LRUCache Features:

Capacity: Limits the number of items in the cache.

OrderedDict: Remembers the order of insertion to evict the least recently used item.

Time to Live (TTL): Items expire after a set duration.

#### Operational Methods:

Get: Retrieves items if they are within TTL, otherwise removes stale entries.

Put: Inserts new items and evicts the oldest if the cache reaches capacity.

#### Integration with AWS S3:

Save to S3: Serializes and saves the current state of the cache to S3 for persistence.

Load from S3: Reloads the cache from S3.

#### Performance Optimization:

Reduces database load by caching frequent queries.

Enhances response times by avoiding repeated data retrieval operations.

User Interface
The user interface is designed using HTML, CSS, and JavaScript to offer a user-friendly experience for querying tweet data.

## How to Use
- Clone this repository.
- Configure AWS credentials.
- Deploy Lambda functions and APIs.
- Access the web application via the provided URL.
- Explore various search options and caching features.

