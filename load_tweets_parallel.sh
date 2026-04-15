#!/bin/sh

files=$(find data/*)

echo '================================================================================'
echo 'load pg_denormalized'
echo '================================================================================'
time echo "$files" | parallel ./load_denormalized.sh

echo '================================================================================'
echo 'load pg_normalized'
echo '================================================================================'
time echo "$files" | parallel python3 load_tweets.py \
    --db "postgresql://postgres:pass@pg_normalized:5432/postgres" \
    --inputs={}

echo '================================================================================'
echo 'load pg_normalized_batch'
echo '================================================================================'
time echo "$files" | parallel python3 -u load_tweets_batch.py \
    --db "postgresql://postgres:pass@pg_normalized_batch:5432/postgres" \
    --inputs={}
