#!/bin/sh

echo '================================================================================'
echo 'load pg_denormalized'
echo '================================================================================'
time python3 load_tweets_batch.py --db postgresql://postgres:pass@localhost:5581/postgres --inputs data/*

echo '================================================================================'
echo 'load pg_normalized'
echo '================================================================================'
time python3 load_tweets.py --db postgresql://postgres:pass@localhost:5582/postgres --inputs data/* --print_every 10000

echo '================================================================================'
echo 'load pg_normalized_batch'
echo '================================================================================'
time python3 -u load_tweets_batch.py --db postgresql://postgres:pass@localhost:5583/postgres --inputs data/*
