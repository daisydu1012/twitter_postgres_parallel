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

    sql = sqlalchemy.sql.text('''
    SELECT id_tweets FROM tweets WHERE id_tweets = :id
    ''')
    if connection.execute(sql, {'id': tweet['id']}).first():
        return

    with connection.begin():

        ################################
        # users
        ################################
        sql = sqlalchemy.sql.text('''
        INSERT INTO users (id_users)
        VALUES (:id)
        ON CONFLICT DO NOTHING
        ''')
        connection.execute(sql, {'id': tweet['user']['id']})

        ################################
        # reply user
        ################################
        if tweet.get('in_reply_to_user_id'):
            connection.execute(sql, {'id': tweet['in_reply_to_user_id']})

        ################################
        # tweet
        ################################
        try:
            text = tweet['extended_tweet']['full_text']
        except:
            text = tweet['text']

        sql = sqlalchemy.sql.text('''
        INSERT INTO tweets (
            id_tweets, id_users, created_at,
            in_reply_to_status_id, in_reply_to_user_id, quoted_status_id,
            retweet_count, favorite_count, quote_count,
            source, text
        )
        VALUES (
            :id, :user, :created,
            :reply_status, :reply_user, :quote,
            :retweet, :fav, :quote_count,
            :source, :text
        )
        ON CONFLICT DO NOTHING
        ''')

        connection.execute(sql, {
            'id': tweet['id'],
            'user': tweet['user']['id'],
            'created': tweet['created_at'],
            'reply_status': tweet.get('in_reply_to_status_id'),
            'reply_user': tweet.get('in_reply_to_user_id'),
            'quote': tweet.get('quoted_status_id'),
            'retweet': tweet.get('retweet_count'),
            'fav': tweet.get('favorite_count'),
            'quote_count': tweet.get('quote_count'),
            'source': tweet.get('source'),
            'text': remove_nulls(text)
        })

        ################################
        # hashtags
        ################################
        try:
            hashtags = tweet['extended_tweet']['entities']['hashtags']
        except:
            hashtags = tweet['entities']['hashtags']

        for tag in hashtags:
            connection.execute(sqlalchemy.sql.text('''
            INSERT INTO tweet_tags (id_tweets, tag)
            VALUES (:id, :tag)
            ON CONFLICT DO NOTHING
            '''), {
                'id': tweet['id'],
                'tag': '#' + tag['text']
            })

        ################################
        # mentions
        ################################
        try:
            mentions = tweet['extended_tweet']['entities']['user_mentions']
        except:
            mentions = tweet['entities']['user_mentions']

        for m in mentions:
            connection.execute(sqlalchemy.sql.text('''
            INSERT INTO users (id_users)
            VALUES (:id)
            ON CONFLICT DO NOTHING
            '''), {'id': m['id']})

            connection.execute(sqlalchemy.sql.text('''
            INSERT INTO tweet_mentions (id_tweets, id_users)
            VALUES (:tweet, :user)
            ON CONFLICT DO NOTHING
            '''), {
                'tweet': tweet['id'],
                'user': m['id']
            })


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--inputs', nargs='+', required=True)
    args = parser.parse_args()

    engine = sqlalchemy.create_engine(args.db)
    connection = engine.connect()

    for filename in sorted(args.inputs):
        print(datetime.datetime.now(), filename)
        with zipfile.ZipFile(filename, 'r') as archive:
            for subfile in archive.namelist():
                with io.TextIOWrapper(archive.open(subfile)) as f:
                    for line in f:
                        tweet = json.loads(line)
                        insert_tweet(connection, tweet)


if __name__ == '__main__':
    main()
