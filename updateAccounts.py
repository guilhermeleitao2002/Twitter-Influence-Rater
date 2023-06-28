import nest_asyncio
import httpx
import time
import asyncio
import psycopg2
import psycopg2.pool
import sys
from gremlin_python.structure.graph import Graph
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from contextlib import contextmanager
from dotenv import load_dotenv
import os
import ssl

# Allow nested asyncio event loops
nest_asyncio.apply()

load_dotenv()
db_config = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

# Create a connection pool to the PostgreSQL database
conn_pool = psycopg2.pool.SimpleConnectionPool(1, 20, **db_config)

@contextmanager
def get_conn_from_pool():
    conn = conn_pool.getconn()
    try:
        yield conn
    finally:
        conn_pool.putconn(conn)

host = 'localhost'
port = '8182'  # Default port for Neptune is 8182
connection_str = f'wss://{host}:{port}/gremlin'

# Establish a connection to Neptune database
try:
    # Create an SSL context and disable SSL verification
    ssl_context = ssl._create_unverified_context()
    # Add the SSL context to the DriverRemoteConnection
    connection = DriverRemoteConnection(connection_str, 'g', ssl=ssl_context)
except Exception as e:
    print(f"Failed to connect to Neptune: {e}")
    sys.exit(1)

# Create a graph instance
graph = Graph()

# Create a traversal source
g = graph.traversal().withRemote(connection)

# Twitter API OAuth 2.0 Bearer Token Configuration
def oauth(r):
    r.headers["Authorization"] = os.getenv('TWITTER_BEARER_TOKEN')
    return r

# Second object being returned is a boolean indicating whether the daily limit cap has been hit
async def get_following(user_id, pageTok):
    url = f"https://api.twitter.com/2/users/{user_id}/following"
    params = {'max_results': 1000, 'user.fields': 'id,name,username,public_metrics'}
    if pageTok is not None:
        params['pagination_token'] = pageTok
    all_followings = []
    count = 0

    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(url, params=params, auth=oauth)
                count += 1
                if response.status_code != 200:

                    if params.get('pagination_token') is not None:
                        # Update the last processed following
                        with open('progress.txt', 'w') as f:
                            f.write(f"{user_id}\n{params['pagination_token']}")

                    if response.status_code == 429:
                        reset_time = float(response.headers.get('X-RateLimit-Reset', 0))
                        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                        
                        # If the remaining limit is zero
                        # Assume the daily cap has been hit and return
                        current_time = time.time()
                        if remaining == 0:
                            print("Daily limit cap hit.")
                            return (all_followings, True)

                        print("Rate limit hit. Waiting and then retrying.")
                        sleep_time = max(0, reset_time - current_time)
                        await asyncio.sleep(sleep_time)
                        continue
                    # Some other error occurred
                    print(f"An error occurred: {response.status_code}\n{response.text}")
                    return (all_followings, True)

                data = response.json()
                all_followings.extend(data['data'])
                if 'next_token' in data['meta']:
                    params['pagination_token'] = data['meta']['next_token']
                else:
                    break

                if 'X-RateLimit-Reset' in response.headers:
                    reset_time = float(response.headers['X-RateLimit-Reset'])
                    current_time = time.time()
                    sleep_time = max(0, reset_time - current_time)
                    await asyncio.sleep(sleep_time)
            except Exception as e:
                print(f"An error occurred: {e}")

    print(f"DEBUG: {count} pages of following data retrieved.")
    print(f"DEBUG: Calls remaining: {response.headers.get('X-RateLimit-Remaining', 0)}")
    return (all_followings, False)

async def is_collection_of_interest(following_id):
    with get_conn_from_pool() as conn:
        try:
            # Open a cursor to perform database operations
            cur = conn.cursor()

            # Execute the query
            cur.execute("SELECT EXISTS\
                        (SELECT 1\
                         FROM public.social_media\
                         WHERE twitter_id = %s\
                         AND tracking = true\
                         AND social_media_sites_id = 1\
                        );", (following_id,))

            # Fetch the result
            result = cur.fetchone()
            return result[0]
        except psycopg2.DatabaseError as error:
            print(f"Database error occurred: {error}")
            return False  # return False or any other value indicating failure
        finally:
            # Close the cursor
            if cur is not None:
                cur.close()

async def updateAccounts():
    # Read the last influencer and following processed
    try:
        with open('progress.txt', 'r') as f:
            last_influencer_processed, last_following_processed_page_token = f.read().splitlines()
    except FileNotFoundError:
        last_influencer_processed, last_following_processed_page_token = None, None

    # Get all influencers in the graph
    influencers = g.V().has('type', 'influencer').order().by('id').toList()

    start_processing = last_influencer_processed is None  # start processing from the beginning if no progress file found

    count_new, count_updated, count_new_collections = 0, 0, 0

    for influencer in influencers:
        influencer_id = g.V(influencer).values('id').next()

        # Skip influencers processed in previous runs
        if influencer_id == last_influencer_processed:
            start_processing = True  # start processing from this influencer
        if not start_processing:
            continue
        
        print(f"\t DEBUG: Processing influencer {g.V(influencer).values('username').next()}")

        # Get the influencer's following from Twitter API
        following_data, apiBurnout = await get_following(influencer_id, last_following_processed_page_token)

        print(f"\t DEBUG: Going to process {len(following_data)} followings.")
        for following in following_data:
            following_id = following['id']
            following_username = following['username']
            following_name = following['name']

            # Get the influencer's metrics from the Twitter API data
            following_metrics = following['public_metrics']
            following_score = 0
            following_count = following_metrics['following_count']
            follower_count = following_metrics['followers_count']
            # If Ronaldo then ignore it
            if follower_count > 5000000:
                continue

            # Determine label based on PostgreSQL check
            # Note: It could technically be an influencer, but it would change nothing
            vertex_type = 'collection' if is_collection_of_interest(following_id) else 'account'

            # Check if the following is already in the graph
            if g.V().has('id', following_id).hasNext():
                # If the following is already in the graph, set the edge
                g.V(influencer_id).addE('follows').to(g.V(following_id)).iterate()

                # Update the following's properties
                # Note: In tinkerpop, you can't update a property, you have to drop it and add it again
                g.V(following_id).properties('username', 'name', 'followers', 'following').drop().iterate()
                g.V(following_id).property('username', following_username)\
                                 .property('name', following_name)\
                                 .property('followers', follower_count)\
                                 .property('following', following_count)\
                                 .iterate()

                if g.V().has('id', following_id).values('type').next() != 'influencer':
                    g.V(following_id).properties('type').drop().iterate()
                    g.V(following_id).property('type', vertex_type).iterate()

                count_updated += 1
            else:
                # If the following is not in the graph, add it with its properties and set the edge                
                g.addV('twitter_account')\
                 .property('id', following_id)\
                 .property('username', following_username)\
                 .property('name', following_name)\
                 .property('influence_score', following_score)\
                 .property('following', following_count)\
                 .property('followers', follower_count)\
                 .property('type', vertex_type).as_('a')\
                 .V(influencer_id).addE('follows').to('a').iterate()

                count_new += 1
                if vertex_type == 'collection':
                    count_new_collections += 1
        
        # Wait 3 seconds before the next influencer
        # Note: This is to help neptune ingest the data
        time.sleep(3)

        # Check if the API limit was hit
        if apiBurnout:
            break

        # The API limit was not hit, so update the state file
        # Update the last processed influencer and reset the last processed following to none
        with open('progress.txt', 'w') as f:
            f.write(f"{influencer_id}\n")

        # Just for debugging
        break

    print(f"DEGUB: Inserted {count_new} new accounts.")
    print(f"DEGUB: Updated {count_updated} existing accounts.")
    print(f"DEGUB: Inserted {count_new_collections} new collections.")
    print(f"DEGUB: Total number of collections: {g.V().has('type', 'collection').count().next()}.")

# asyncio.run is the main entry point for asyncio programs and is used to run the top-level coroutine and creates a new event loop
asyncio.run(updateAccounts())

# Close the connection
connection.close()

# Close the database connection
conn_pool.closeall()