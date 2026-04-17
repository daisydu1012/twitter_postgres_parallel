#!/usr/bin/python3

import sqlalchemy
import datetime
import zipfile
import io
import json


def remove_nulls(s):
    if s is None:
        return None
    return s.replace('\x00', '\\x00')


def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]


def _bulk_insert_sql(table, rows):
    if not rows:
        return None, None

    keys = sorted(rows[0].keys())
    sql = (
        f"INSERT INTO {table} (" + ",".join(keys) + ") VALUES " +
        ",".join(
            ["(" + ",".join([f":{key}{i}" for key in keys]) + ")" for i in range(len(rows))]
        ) +
        " ON CONFLICT DO NOTHING"
    )
    binds = {
        key + str(i): value
        for i, row in enumerate(rows)
        for key, value in row.items()
    }
    return sql, binds


def bulk_insert(connection, table, rows):
    if len(rows) == 0:
        return
    sql, binds = _bulk_insert_sql(table, rows)
    connection.execute(sqlalchemy.sql.text(sql), binds)


def insert_users_one_by_one(connection, rows):
    if len(rows) == 0:
        return

    keys = sorted(rows[0].keys())
    sql = (
        f"INSERT INTO users (" + ",".join(keys) + ") VALUES (" +
        ",".join([f":{key}" for key in keys]) +
        ") ON CONFLICT DO NOTHING"
    )
    stmt = sqlalchemy.sql.text(sql)

    for row in sorted(rows, key=lambda r: (r.get('id_users') is None, r.get('id_users'))):
        connection.execute(stmt, row)


def insert_tweets(connection, tweets, batch_size=1000):
    for i, tweet_batch in enumerate(batch(tweets, batch_size)):
        print(datetime.datetime.now(), 'insert_tweets i=', i)

        # ❗没有 transaction（避免 deadlock）
        _insert_tweets(connection, tweet_batch)


def _insert_tweets(connection, input_tweets):
    users = []
    tweets = []
    users_unhydrated_from_tweets = []
    users_unhydrated_from_mentions = []
    tweet_mentions = []
    tweet_tags = []
    tweet_media = []
    tweet_urls = []

    for tweet in input_tweets:

        # ---------------- users ----------------
        users.append({
            'id_users': tweet['user']['id'],
            'created_at': tweet['user']['created_at'],
            'updated_at': tweet['created_at'],
            'screen_name': remove_nulls(tweet['user']['screen_name']),
            'name': remove_nulls(tweet['user']['name']),
            'location': remove_nulls(tweet['user']['location']),
            'url': remove_nulls(tweet['user'].get('url')),
            'description': remove_nulls(tweet['user']['description']),
            'protected': tweet['user']['protected'],
            'verified': tweet['user']['verified'],
            'friends_count': tweet['user']['friends_count'],
            'listed_count': tweet['user']['listed_count'],
            'favourites_count': tweet['user']['favourites_count'],
            'statuses_count': tweet['user']['statuses_count'],
            'withheld_in_countries': tweet['user'].get('withheld_in_countries'),
        })

        # ---------------- geo ----------------
        try:
            geo_coords = str(tweet['geo']['coordinates'][0]) + ' ' + str(tweet['geo']['coordinates'][1])
            geo_str = 'POINT'
        except:
            geo_coords = None
            geo_str = None

        # ---------------- text ----------------
        try:
            text = tweet['extended_tweet']['full_text']
        except:
            text = tweet['text']

        # ---------------- location ----------------
        try:
            country_code = tweet['place']['country_code'].lower()
        except:
            country_code = None

        if country_code == 'us':
            try:
                state_code = tweet['place']['full_name'].split(',')[-1].strip().lower()
                if len(state_code) > 2:
                    state_code = None
            except:
                state_code = None
        else:
            state_code = None

        try:
            place_name = tweet['place']['full_name']
        except:
            place_name = None

        # ---------------- reply user ----------------
        if tweet.get('in_reply_to_user_id'):
            users_unhydrated_from_tweets.append({
                'id_users': tweet['in_reply_to_user_id'],
            })

        # ---------------- tweets ----------------
        tweets.append({
            'id_tweets': tweet['id'],
            'id_users': tweet['user']['id'],
            'created_at': tweet['created_at'],
            'in_reply_to_status_id': tweet.get('in_reply_to_status_id'),
            'in_reply_to_user_id': tweet.get('in_reply_to_user_id'),
            'quoted_status_id': tweet.get('quoted_status_id'),
            'geo_coords': geo_coords,
            'geo_str': geo_str,
            'retweet_count': tweet.get('retweet_count'),
            'quote_count': tweet.get('quote_count'),
            'favorite_count': tweet.get('favorite_count'),
            'withheld_copyright': tweet.get('withheld_copyright'),
            'withheld_in_countries': tweet.get('withheld_in_countries'),
            'place_name': place_name,
            'country_code': country_code,
            'state_code': state_code,
            'lang': tweet.get('lang'),
            'text': remove_nulls(text),
            'source': remove_nulls(tweet.get('source')),
        })

        # ---------------- mentions ----------------
        for mention in tweet.get('entities', {}).get('user_mentions', []):
            users_unhydrated_from_mentions.append({
                'id_users': mention['id'],
            })
            tweet_mentions.append({
                'id_tweets': tweet['id'],
                'id_users': mention['id'],
            })

        # ---------------- tags ----------------
        for h in tweet.get('entities', {}).get('hashtags', []):
            tweet_tags.append({
                'id_tweets': tweet['id'],
                'tag': '#' + h['text']
            })

        for s in tweet.get('entities', {}).get('symbols', []):
            tweet_tags.append({
                'id_tweets': tweet['id'],
                'tag': '$' + s['text']
            })

        # ---------------- urls ----------------
        for url in tweet.get('entities', {}).get('urls', []):
            tweet_urls.append({
                'id_tweets': tweet['id'],
                'url': remove_nulls(url.get('expanded_url'))
            })

        # ---------------- media ----------------
        for m in tweet.get('entities', {}).get('media', []):
            tweet_media.append({
                'id_tweets': tweet['id'],
                'url': remove_nulls(m.get('media_url')),
                'type': remove_nulls(m.get('type'))
            })

    # ✅ users first
    insert_users_one_by_one(connection, users)
    insert_users_one_by_one(connection, users_unhydrated_from_tweets)
    insert_users_one_by_one(connection, users_unhydrated_from_mentions)

    # ✅ tweets second（关键）
    sql_tweet = sqlalchemy.sql.text("""
        INSERT INTO tweets (
            id_tweets,id_users,created_at,in_reply_to_status_id,in_reply_to_user_id,
            quoted_status_id,geo,retweet_count,quote_count,favorite_count,
            withheld_copyright,withheld_in_countries,place_name,country_code,
            state_code,lang,text,source
        ) VALUES (
            :id_tweets,:id_users,:created_at,:in_reply_to_status_id,:in_reply_to_user_id,
            :quoted_status_id,
            ST_GeomFromText(:geo_str || '(' || :geo_coords || ')'),
            :retweet_count,:quote_count,:favorite_count,
            :withheld_copyright,:withheld_in_countries,:place_name,
            :country_code,:state_code,:lang,:text,:source
        )
        ON CONFLICT DO NOTHING
    """)

    for t in tweets:
        connection.execute(sql_tweet, t)

    # ✅ dependent tables LAST（关键）
    bulk_insert(connection, 'tweet_mentions', tweet_mentions)
    bulk_insert(connection, 'tweet_tags', tweet_tags)
    bulk_insert(connection, 'tweet_media', tweet_media)
    bulk_insert(connection, 'tweet_urls', tweet_urls)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--inputs', nargs='+', required=True)
    parser.add_argument('--batch_size', type=int, default=1000)
    args = parser.parse_args()

    engine = sqlalchemy.create_engine(args.db)
    connection = engine.connect()

    for filename in sorted(args.inputs, reverse=True):
        with zipfile.ZipFile(filename, 'r') as archive:
            print(datetime.datetime.now(), filename)
            for subfilename in sorted(archive.namelist(), reverse=True):
                with io.TextIOWrapper(archive.open(subfilename)) as f:
                    tweets = [json.loads(line) for line in f]
                    insert_tweets(connection, tweets, args.batch_size)
