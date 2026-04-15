#!/bin/bash
for file in "$@"; do
    python3 -u load_tweets.py --db=postgresql://postgres:pass@localhost:5581/postgres --inputs $file
done
