#!/bin/sh

echo '================================================================================'
echo 'load pg_denormalized'
echo '================================================================================'
time sh load_denormalized.sh data/*

echo '================================================================================'
echo 'load pg_normalized'
echo '================================================================================'
for f in data/*; do
    python3 load_tweets.py \
        --db postgresql://postgres:pass@localhost:5582/postgres \
        --inputs "$f" \
        --print_every 10000
done

echo '================================================================================'
echo 'load pg_normalized_batch'
echo '================================================================================'
for f in data/*; do
    python3 -u load_tweets_batch.py \
        --db postgresql://postgres:pass@localhost:5583/postgres \
        --inputs "$f"
done
