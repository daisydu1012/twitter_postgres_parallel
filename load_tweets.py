#!/usr/bin/python3

import sqlalchemy
import zipfile
import json


def remove_nulls(s):
    if s is None:
        return None
    return s.replace('\x00', '')


def get_id_urls(connection, url):
    if url is None:
        return None

    url = remove_nulls(url)

    sql = sqlalchemy.sql.text("""
        INSERT INTO urls (url)
        VALUES (:url)
        ON CONFLICT DO NOTHING
        RETURNING id_urls
    """)
    res = connection.execute(sql, {'url': url}).first()

    if res is None:
        sql = sqlalchemy.sql.text("""
            SELECT id_urls
            FROM urls
            WHERE url = :url
        """)
        res = connection.execute(sql, {'url': url}).first()

    return res[0]


def insert_tweet(connection, tweet):

    # skip if exists
    sql = sqlalchemy.sql.text("""
    SELECT id_tweets FROM tweets WHERE id_tweets = :id
    """)
    if connection.execute(sql, {'id': tweet['id']}).first():
        return

    with connection.begin():

        # ------------------------
        # users (author)
        # ------------------------
        connection.execute(sqlalchemy.sql.text("""
            INSERT INTO users (id_users)
            VALUES (:id)
            ON CONFLICT DO NOTHING
        """), {
            'id': tweet['user']['id']
        })

        # reply user
        if tweet.get('in_reply_to_user_id') is not None:
            connection.execute(sqlalchemy.sql.text("""
                INSERT INTO users (id_users)
                VALUES (:id)
                ON CONFLICT DO NOTHING
            """), {
                'id': tweet['in_reply_to_user_id']
            })

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
        connection.execute(sqlalchemy.sql.text("""
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
        """), {
            'id': tweet['id'],
            'user': tweet['user']['id'],
            'created': tweet.get('created_at'),
            'reply_status': tweet.get('in_reply_to_status_id'),
            'reply_user': tweet.get('in_reply_to_user_id'),
            'quote': tweet.get('quoted_status_id'),
            'retweet': tweet.get('retweet_count', 0),
            'favorite': tweet.get('favorite_count', 0),
            'quote_count': tweet.get('quote_count', 0),
            'source': remove_nulls(tweet.get('source')),
            'text': text
        })

        # ------------------------
        # hashtags
        # ------------------------
        try:
            hashtags = tweet['extended_tweet']['entities']['hashtags']
        except:
            hashtags = tweet.get('entities', {}).get('hashtags', [])

        for tag in hashtags:
            connection.execute(sqlalchemy.sql.text("""
                INSERT INTO tweet_tags (id_tweets, tag)
                VALUES (:id, :tag)
                ON CONFLICT DO NOTHING
            """), {
                'id': tweet['id'],
                'tag': remove_nulls(tag['text'].lower())
            })

        # ------------------------
        # mentions
        # ------------------------
        try:
            mentions = tweet['extended_tweet']['entities']['user_mentions']
        except:
            mentions = tweet.get('entities', {}).get('user_mentions', [])

        for mention in mentions:

            # insert mentioned user FIRST
            connection.execute(sqlalchemy.sql.text("""
                INSERT INTO users (id_users)
                VALUES (:id_users)
                ON CONFLICT DO NOTHING
            """), {
                'id_users': mention['id']
            })

            # then insert mention
            connection.execute(sqlalchemy.sql.text("""
                INSERT INTO tweet_mentions (id_tweets, id_users)
                VALUES (:id_tweets, :id_users)
                ON CONFLICT DO NOTHING
            """), {
                'id_tweets': tweet['id'],
                'id_users': mention['id']
            })

        # ------------------------
        # urls
        # ------------------------
        try:
            urls = tweet['extended_tweet']['entities']['urls']
        except:
            urls = tweet.get('entities', {}).get('urls', [])

        for u in urls:
            expanded_url = u.get('expanded_url')
            id_url = get_id_urls(connection, expanded_url)

            if id_url is not None:
                connection.execute(sqlalchemy.sql.text("""
                    INSERT INTO tweet_urls (id_tweets, id_urls)
                    VALUES (:id, :id_url)
                    ON CONFLICT DO NOTHING
                """), {
                    'id': tweet['id'],
                    'id_url': id_url
                })

        # ------------------------
        # media
        # ------------------------
        media = tweet.get('extended_entities', {}).get('media', [])
        for m in media:
            media_url = m.get('media_url')
            id_url = get_id_urls(connection, media_url)

            if id_url is not None:
                connection.execute(sqlalchemy.sql.text("""
                    INSERT INTO tweet_media (id_tweets, id_urls, type)
                    VALUES (:id, :id_url, :type)
                    ON CONFLICT DO NOTHING
                """), {
                    'id': tweet['id'],
                    'id_url': id_url,
                    'type': remove_nulls(m.get('type'))
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
