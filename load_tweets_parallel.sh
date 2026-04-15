#!/bin/sh

echo '================================================================================'
echo 'load pg_denormalized'
echo '================================================================================'
time parallel ./load_denormalized.sh ::: data/*

echo '================================================================================'
echo 'load pg_normalized'
echo '================================================================================'
time parallel 'python3 load_tweets.py --db postgresql://postgres:pass@pg_normalized:5432/postgres --inputs {} --print_every 10000' ::: data/*

echo '================================================================================'
echo 'load pg_normalized_batch'
echo '================================================================================'
time parallel 'python3 -u load_tweets_batch.py --db=postgresql://postgres:pass@pg_normalized_batch:5432/postgres --inputs {}' ::: data/*
