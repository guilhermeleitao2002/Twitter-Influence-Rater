# Social Media Graph Management System

This repository contains scripts to manage and analyze social media data stored in an Amazon Neptune graph database. The system synchronizes Twitter following data, calculates influence scores, and performs routine cleanups.

## Overview

The system consists of three main scripts:
1. **updateAccounts.py**: Syncs Twitter following data into the graph database.
2. **calculateInfluenceScore.py**: Computes influence scores using a custom PageRank-like algorithm.
3. **performRoutineCleanUp.py**: Removes low-influence accounts from the graph.

## Scripts

### 1. `updateAccounts.py`
- **Purpose**: Fetches an influencer's Twitter followings and updates the graph database.
- **Key Features**:
  - Connects to PostgreSQL (for tracking collections) and Neptune (graph DB).
  - Uses Twitter API v2 to retrieve followings with pagination and rate limit handling.
  - Adds/updates nodes (accounts/collections) and edges (`follows` relationships).
  - Tracks progress using `progress.txt` to resume after interruptions.
  - Skips accounts with >5M followers (e.g., celebrities like Ronaldo).

### 2. `calculateInfluenceScore.py`
- **Purpose**: Computes influence scores for non-influencer nodes.
- **Key Features**:
  - Implements a simplified PageRank algorithm:
    - Score = Σ (Inbound node's score / Outbound degree of inbound node).
  - Updates scores iteratively (configurable with `max_iterations`).
  - Avoids influencers (nodes marked as `type=influencer`).

### 3. `performRoutineCleanUp.py`
- **Purpose**: Removes low-impact accounts from the graph.
- **Key Features**:
  - Deletes accounts with an influence score below the current average.
  - Targets nodes marked as `type=account`.

## Prerequisites
- Python 3.9+
- Libraries:  
  ```bash
  pip install nest-asyncio httpx psycopg2-binary gremlinpython python-dotenv
  ```
- Databases:
  - **PostgreSQL**: Stores tracked collections (`social_media` table).
  - **Amazon Neptune**: Graph database for storing accounts and relationships.
- Twitter API v2 Bearer Token (for `updateAccounts.py`).

## Configuration
1. Create a `.env` file with:
   ```ini
   DB_NAME=your_db_name
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_HOST=your_db_host
   DB_PORT=your_db_port
   TWITTER_BEARER_TOKEN=your_twitter_bearer_token
   ```
2. Ensure Neptune is running at `localhost:8182` (modify `host`/`port` in scripts if needed).

## Usage
1. **Sync Data** (Run first):
   ```bash
   python updateAccounts.py
   ```
2. **Calculate Influence Scores** (Run periodically):
   ```bash
   python calculateInfluenceScore.py
   ```
3. **Clean Up Graph** (Run after score updates):
   ```bash
   python performRoutineCleanUp.py
   ```

## Notes
- **Order**: Run scripts in sequence: `updateAccounts.py` → `calculateInfluenceScore.py` → `performRoutineCleanUp.py`.
- **Rate Limits**: `updateAccounts.py` handles Twitter API rate limits and daily caps.
- **Security**: SSL verification is disabled for Neptune connections (not recommended for production).
- **Progress Tracking**: `progress.txt` stores the last processed influencer and pagination token.
- **Performance**: A 3-second delay between influencers in `updateAccounts.py` ensures Neptune stability.

For questions or issues, contact the repository maintainer.
