#!/usr/bin/python3

import sqlalchemy
import datetime
import zipfile
import io
import json


def remove_nulls(s):
    if s is None:
        return None
    return s.replace('\x00', '')


def insert_tweet(connection, tweet):

    # skip if exists
    sql = sqlalchemy.sql.text("""
    SELECT id_tweets FROM tweets WHERE id_tweets = :id
    """)
    if connection.execute(sql, {'id': tweet['id']}).first():
        return

    with connection.begin():

        # ------------------------
        # users
        # ------------------------
        sql = sqlalchemy.sql.text("""
        INSERT INTO users (id_users)
        VALUES (:id)
        ON CONFLICT DO NOTHING
        """)
        connection.execute(sql, {'id': tweet['user']['id']})

        if tweet.get('in_reply_to_user_id'):
            connection.execute(sql, {'id': tweet['in_reply_to_user_id']})

        # ------------------------
        # tweet text
        # ------------------------
        try:
            text = tweet['extended_tweet']['full_text']
        except:
            text = tweet.get('text')

        text = remove_nulls(text)

        # ------------------------
        # insert tweet
        # ------------------------
        sql = sqlalchemy.sql.text("""
        INSERT INTO tweets (
            id_tweets, id_users, created_at,
            in_reply_to_status_id, in_reply_to_user_id, quoted_status_id,
            retweet_count, favorite_count, quote_count,
            source, text
        )
        VALUES (
            :id, :user, :created,
            :reply_status, :reply_user, :quote,
            :retweet, :favorite, :quote_count,
            :source, :text
        )
        """)

        connection.execute(sql, {
            'id': tweet['id'],
            'user': tweet['user']['id'],
            'created': tweet.get('created_at'),
            'reply_status': tweet.get('in_reply_to_status_id'),
            'reply_user': tweet.get('in_reply_to_user_id'),
            'quote': tweet.get('quoted_status_id'),
            'retweet': tweet.get('retweet_count', 0),
            'favorite': tweet.get('favorite_count', 0),
            'quote_count': tweet.get('quote_count', 0),
            'source': tweet.get('source'),
            'text': text
        })

        # ------------------------
        # hashtags
        # ------------------------
        for tag in tweet.get('entities', {}).get('hashtags', []):
            connection.execute(sqlalchemy.sql.text("""
            INSERT INTO tweet_tags (id_tweets, tag)
            VALUES (:id, :tag)
            ON CONFLICT DO NOTHING
            """), {
                'id': tweet['id'],
                'tag': tag['text'].lower()
            })

        # ------------------------
        # mentions
        # ------------------------
        for m in tweet.get('entities', {}).get('user_mentions', []):
            connection.execute(sqlalchemy.sql.text("""
            INSERT INTO tweet_mentions (id_tweets, id_users)
            VALUES (:id_tweets, :id_users)
            ON CONFLICT DO NOTHING
            """), {
                'id_tweets': tweet['id'],
                'id_users': m['id']
            })

        # ------------------------
        # urls
        # ------------------------
        for u in tweet.get('entities', {}).get('urls', []):
            connection.execute(sqlalchemy.sql.text("""
            INSERT INTO tweet_urls (id_tweets, url)
            VALUES (:id, :url)
            ON CONFLICT DO NOTHING
            """), {
                'id': tweet['id'],
                'url': u.get('expanded_url')
            })

        # ------------------------
        # media
        # ------------------------
        media = tweet.get('extended_entities', {}).get('media', [])
        for m in media:
            connection.execute(sqlalchemy.sql.text("""
            INSERT INTO tweet_media (id_tweets, url, type)
            VALUES (:id, :url, :type)
            ON CONFLICT DO NOTHING
            """), {
                'id': tweet['id'],
                'url': m.get('media_url'),
                'type': m.get('type')
            })


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--inputs', nargs='+', required=True)
    parser.add_argument('--print_every', type=int, default=10000)
    args = parser.parse_args()

    engine = sqlalchemy.create_engine(args.db)

    connection = engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    )

    i = 0

    for filename in args.inputs:
        print(filename)

        with zipfile.ZipFile(filename) as z:
            for name in z.namelist():
                with z.open(name) as f:
                    for line in f:
                        tweet = json.loads(line)
                        insert_tweet(connection, tweet)

                        if i % args.print_every == 0:
                            print(f"{filename} - i= {i} id= {tweet['id']}")
                        i += 1


if __name__ == "__main__":
    main()
