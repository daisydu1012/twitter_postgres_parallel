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
    sql = sqlalchemy.sql.text('''
    SELECT id_tweets FROM tweets WHERE id_tweets = :id
    ''')
    if connection.execute(sql, {'id': tweet['id']}).first():
        return

    # transaction
    with connection.begin():

        ########################################
        # users
        ########################################
        sql = sqlalchemy.sql.text('''
        INSERT INTO users (
            id_users, created_at, updated_at,
            screen_name, name, location, description,
            protected, verified,
            friends_count, listed_count, favourites_count, statuses_count,
            withheld_in_countries
        )
        VALUES (
            :id_users, :created_at, :updated_at,
            :screen_name, :name, :location, :description,
            :protected, :verified,
            :friends_count, :listed_count, :favourites_count, :statuses_count,
            :withheld_in_countries
        )
        ON CONFLICT DO NOTHING
        ''')

        connection.execute(sql, {
            'id_users': tweet['user']['id'],
            'created_at': tweet['user']['created_at'],
            'updated_at': tweet['created_at'],
            'screen_name': tweet['user']['screen_name'],
            'name': tweet['user']['name'],
            'location': tweet['user']['location'],
            'description': tweet['user']['description'],
            'protected': tweet['user']['protected'],
            'verified': tweet['user']['verified'],
            'friends_count': tweet['user']['friends_count'],
            'listed_count': tweet['user']['listed_count'],
            'favourites_count': tweet['user']['favourites_count'],
            'statuses_count': tweet['user']['statuses_count'],
            'withheld_in_countries': tweet['user'].get('withheld_in_countries', [])
        })

        ########################################
        # ensure reply user exists
        ########################################
        if tweet.get('in_reply_to_user_id'):
            sql = sqlalchemy.sql.text('''
            INSERT INTO users (id_users)
            VALUES (:id)
            ON CONFLICT DO NOTHING
            ''')
            connection.execute(sql, {'id': tweet['in_reply_to_user_id']})

        ########################################
        # tweets
        ########################################

        try:
            text = tweet['extended_tweet']['full_text']
        except:
            text = tweet['text']

        sql = sqlalchemy.sql.text('''
        INSERT INTO tweets (
            id_tweets, id_users, created_at,
            in_reply_to_status_id, in_reply_to_user_id, quoted_status_id,
            retweet_count, favorite_count, quote_count,
            withheld_copyright, withheld_in_countries,
            source, text
        )
        VALUES (
            :id, :user, :created,
            :reply_status, :reply_user, :quote,
            :retweet, :fav, :quote_count,
            :copyright, :countries,
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
            'copyright': tweet.get('withheld_copyright'),
            'countries': tweet.get('withheld_in_countries'),
            'source': tweet.get('source'),
            'text': remove_nulls(text)
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
