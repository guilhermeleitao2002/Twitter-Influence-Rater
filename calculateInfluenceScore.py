import nest_asyncio
import asyncio
from gremlin_python.structure.graph import Graph
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
import sys
import ssl

# Allow nested asyncio event loops
nest_asyncio.apply()

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

async def run_pagerank(max_iterations=1):
    try:
        vertices = g.V().toList()
    except Exception as e:
        print(f"Failed to fetch vertices from Neptune: {e}")
        return

    # For each iteration
    for _ in range(max_iterations):
        # Calculate the new rank for each vertex
        for vertex in vertices:
            try:
                print(f"DEBUG: Updating rank for vertex {vertex}")
                if not g.V(vertex).has('type', 'influencer').hasNext():
                    inbound_vertices = g.V(vertex).in_().toList()
                    rank_sum = 0
                    for inbound_vertex in inbound_vertices:
                        outbound_count = g.V(inbound_vertex).out().count().next()
                        rank_sum += g.V(inbound_vertex).values('influence_score').to_list()[0] / outbound_count
                    g.V(vertex).properties('influence_score').drop().iterate()
                    g.V(vertex).property('influence_score', rank_sum).next()
            except Exception as e:
                print(f"Failed to update rank for vertex {vertex}: {e}")

        # Wait a bit for Neptune to finish processing all the updates from this iteration
        await asyncio.sleep(3)

asyncio.run(run_pagerank())

# Close the connection
connection.close()