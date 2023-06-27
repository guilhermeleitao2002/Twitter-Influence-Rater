import nest_asyncio
import asyncio
import sys
from gremlin_python.structure.graph import Graph
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
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

async def run_cleanup():
    try:
        vertices = g.V().toList()
        avg = g.V().values('influence_score').mean().next()

        for vertex in vertices:
            if g.V(vertex).has('type', 'account').hasNext() and\
            g.V(vertex).values('influence_score').toList()[0] < avg:
                g.V(vertex).drop().iterate().next()  # irrelevant

    except Exception as e:
        print(f"An error occurred while cleaning up the graph: {e}")

asyncio.run(run_cleanup())

# Close the connection
connection.close()
