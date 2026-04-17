#!/usr/bin/python3

import sqlalchemy
import zipfile
import json
import datetime
import io


def remove_nulls(s):
    if s is None:
        return None
    return s.replace('\x00', '')


def detect_schema(connection):
    # denormalized: raw jsonb table exists
    res = connection.execute(sqlalchemy.sql.text("""
        SELECT to_regclass('public.tweets_jsonb')
    """)).first()
    if res is not None and res[0] is not None:
        return 'denormalized'

    # normalized vs normalized_batch:
    # normalized has users.id_urls and tweet_urls.id_urls
    res = connection.execute(sqlalchemy.sql.text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'tweet_urls'
    """))
    tweet_url_cols = {row[0] for row in res}

    if 'id_urls' in tweet_url_cols:
        return 'normalized'

    return 'normalized_batch'


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


def insert_denormalized_tweet(connection, tweet):
    sql = sqlalchemy.sql.text("""
        INSERT INTO tweets_jsonb (data)
        VALUES (CAST(:data AS JSONB))
    """)
    connection.execute(sql, {'data': json.dumps(tweet)})


def build_geo(tweet):
    try:
        coords = tweet['geo']['coordinates']
        if coords is not None:
            geo_coords = f"{coords[0]} {coords[1]}"
            return f"POINT({geo_coords})"
    except Exception:
        pass

    try:
        polygons = tweet['place']['bounding_box']['coordinates']
        if polygons is not None:
            geo_coords = "("
            for i, poly in enumerate(polygons):
                if i > 0:
                    geo_coords += ","
                geo_coords += "("
                for point in poly:
                    geo_coords += f"{point[0]} {point[1]},"
                geo_coords += f"{poly[0][0]} {poly[0][1]}"
                geo_coords += ")"
            geo_coords += ")"
            return f"MULTIPOLYGON({geo_coords})"
    except Exception:
        pass

    return None


def build_location_fields(tweet):
    try:
        country_code = tweet['place']['country_code'].lower()
    except Exception:
        country_code = None

    if country_code == 'us':
        try:
            state_code = tweet['place']['full_name'].split(',')[-1].strip().lower()
            if len(state_code) > 2:
                state_code = None
        except Exception:
            state_code = None
    else:
        state_code = None

    try:
        place_name = tweet['place']['full_name']
    except Exception:
        place_name = None

    return (
        remove_nulls(country_code),
        remove_nulls(state_code),
        remove_nulls(place_name),
    )


def get_full_text(tweet):
    try:
        return remove_nulls(tweet['extended_tweet']['full_text'])
    except Exception:
        return remove_nulls(tweet.get('text'))


def get_entities_list(tweet, key):
    try:
        return tweet['extended_tweet']['entities'][key]
    except Exception:
        return tweet.get('entities', {}).get(key, [])


def get_media_list(tweet):
    try:
        return tweet['extended_tweet']['extended_entities']['media']
    except Exception:
        try:
            return tweet['extended_entities']['media']
        except Exception:
            return []


def insert_user(connection, tweet, schema_type):
    user = tweet['user']

    if schema_type == 'normalized':
        if user.get('url') is None:
            user_id_urls = None
        else:
            user_id_urls = get_id_urls(connection, user.get('url'))

        sql = sqlalchemy.sql.text("""
            INSERT INTO users (
                id_users,
                created_at,
                updated_at,
                id_urls,
                friends_count,
                listed_count,
                favourites_count,
                statuses_count,
                protected,
                verified,
                screen_name,
                name,
                location,
                description,
                withheld_in_countries
            ) VALUES (
                :id_users,
                :created_at,
                :updated_at,
                :id_urls,
                :friends_count,
                :listed_count,
                :favourites_count,
                :statuses_count,
                :protected,
                :verified,
                :screen_name,
                :name,
                :location,
                :description,
                :withheld_in_countries
            )
            ON CONFLICT DO NOTHING
        """)
        connection.execute(sql, {
            'id_users': user['id'],
            'created_at': remove_nulls(user.get('created_at')),
            'updated_at': None,
            'id_urls': user_id_urls,
            'friends_count': user.get('friends_count'),
            'listed_count': user.get('listed_count'),
            'favourites_count': user.get('favourites_count'),
            'statuses_count': user.get('statuses_count'),
            'protected': user.get('protected'),
            'verified': user.get('verified'),
            'screen_name': remove_nulls(user.get('screen_name')),
            'name': remove_nulls(user.get('name')),
            'location': remove_nulls(user.get('location')),
            'description': remove_nulls(user.get('description')),
            'withheld_in_countries': user.get('withheld_in_countries'),
        })

    elif schema_type == 'normalized_batch':
        sql = sqlalchemy.sql.text("""
            INSERT INTO users (
                id_users,
                created_at,
                updated_at,
                url,
                friends_count,
                listed_count,
                favourites_count,
                statuses_count,
                protected,
                verified,
                screen_name,
                name,
                location,
                description,
                withheld_in_countries
            ) VALUES (
                :id_users,
                :created_at,
                :updated_at,
                :url,
                :friends_count,
                :listed_count,
                :favourites_count,
                :statuses_count,
                :protected,
                :verified,
                :screen_name,
                :name,
                :location,
                :description,
                :withheld_in_countries
            )
            ON CONFLICT DO NOTHING
        """)
        connection.execute(sql, {
            'id_users': user['id'],
            'created_at': remove_nulls(user.get('created_at')),
            'updated_at': None,
            'url': remove_nulls(user.get('url')),
            'friends_count': user.get('friends_count'),
            'listed_count': user.get('listed_count'),
            'favourites_count': user.get('favourites_count'),
            'statuses_count': user.get('statuses_count'),
            'protected': user.get('protected'),
            'verified': user.get('verified'),
            'screen_name': remove_nulls(user.get('screen_name')),
            'name': remove_nulls(user.get('name')),
            'location': remove_nulls(user.get('location')),
            'description': remove_nulls(user.get('description')),
            'withheld_in_countries': user.get('withheld_in_countries'),
        })


def insert_unhydrated_user(connection, user_id):
    if user_id is None:
        return

    sql = sqlalchemy.sql.text("""
        INSERT INTO users (id_users)
        VALUES (:id_users)
        ON CONFLICT DO NOTHING
    """)
    connection.execute(sql, {'id_users': user_id})


def insert_tweet(connection, tweet, schema_type):
    if schema_type == 'denormalized':
        insert_denormalized_tweet(connection, tweet)
        return

    # skip tweet if already inserted
    sql = sqlalchemy.sql.text("""
        SELECT id_tweets
        FROM tweets
        WHERE id_tweets = :id_tweets
    """)
    res = connection.execute(sql, {'id_tweets': tweet['id']})
    if res.first() is not None:
        return

    with connection.begin():
        insert_user(connection, tweet, schema_type)

        # ensure in_reply_to_user_id exists for FK schemas / batch tables
        insert_unhydrated_user(connection, tweet.get('in_reply_to_user_id'))

        text = get_full_text(tweet)
        geo_wkt = build_geo(tweet)
        country_code, state_code, place_name = build_location_fields(tweet)

        sql = sqlalchemy.sql.text("""
            INSERT INTO tweets (
                id_tweets,
                id_users,
                created_at,
                in_reply_to_status_id,
                in_reply_to_user_id,
                quoted_status_id,
                retweet_count,
                favorite_count,
                quote_count,
                withheld_copyright,
                withheld_in_countries,
                source,
                text,
                country_code,
                state_code,
                lang,
                place_name,
                geo
            )
            VALUES (
                :id_tweets,
                :id_users,
                :created_at,
                :in_reply_to_status_id,
                :in_reply_to_user_id,
                :quoted_status_id,
                :retweet_count,
                :favorite_count,
                :quote_count,
                :withheld_copyright,
                :withheld_in_countries,
                :source,
                :text,
                :country_code,
                :state_code,
                :lang,
                :place_name,
                ST_GeomFromText(:geo)
            )
            ON CONFLICT DO NOTHING
        """)
        connection.execute(sql, {
            'id_tweets': tweet['id'],
            'id_users': tweet['user']['id'],
            'created_at': remove_nulls(tweet.get('created_at')),
            'in_reply_to_status_id': tweet.get('in_reply_to_status_id'),
            'in_reply_to_user_id': tweet.get('in_reply_to_user_id'),
            'quoted_status_id': tweet.get('quoted_status_id'),
            'retweet_count': tweet.get('retweet_count'),
            'favorite_count': tweet.get('favorite_count'),
            'quote_count': tweet.get('quote_count'),
            'withheld_copyright': tweet.get('withheld_copyright'),
            'withheld_in_countries': tweet.get('withheld_in_countries'),
            'source': remove_nulls(tweet.get('source')),
            'text': text,
            'country_code': country_code,
            'state_code': state_code,
            'lang': remove_nulls(tweet.get('lang')),
            'place_name': place_name,
            'geo': geo_wkt,
        })

        # urls
        urls = get_entities_list(tweet, 'urls')
        for url in urls:
            expanded_url = remove_nulls(url.get('expanded_url'))
            if expanded_url is None:
                continue

            if schema_type == 'normalized':
                id_urls = get_id_urls(connection, expanded_url)
                sql = sqlalchemy.sql.text("""
                    INSERT INTO tweet_urls (id_tweets, id_urls)
                    VALUES (:id_tweets, :id_urls)
                    ON CONFLICT DO NOTHING
                """)
                connection.execute(sql, {
                    'id_tweets': tweet['id'],
                    'id_urls': id_urls,
                })
            else:
                sql = sqlalchemy.sql.text("""
                    INSERT INTO tweet_urls (id_tweets, url)
                    VALUES (:id_tweets, :url)
                    ON CONFLICT DO NOTHING
                """)
                connection.execute(sql, {
                    'id_tweets': tweet['id'],
                    'url': expanded_url,
                })

        # mentions
        mentions = get_entities_list(tweet, 'user_mentions')
        for mention in mentions:
            mention_id = mention.get('id')
            if mention_id is None:
                continue

            insert_unhydrated_user(connection, mention_id)

            sql = sqlalchemy.sql.text("""
                INSERT INTO tweet_mentions (id_tweets, id_users)
                VALUES (:id_tweets, :id_users)
                ON CONFLICT DO NOTHING
            """)
            connection.execute(sql, {
                'id_tweets': tweet['id'],
                'id_users': mention_id,
            })

        # tags: hashtags + cashtags
        hashtags = get_entities_list(tweet, 'hashtags')
        symbols = get_entities_list(tweet, 'symbols')

        tags = (
            ['#' + remove_nulls(tag['text']) for tag in hashtags if tag.get('text') is not None] +
            ['$' + remove_nulls(tag['text']) for tag in symbols if tag.get('text') is not None]
        )

        for tag in tags:
            sql = sqlalchemy.sql.text("""
                INSERT INTO tweet_tags (id_tweets, tag)
                VALUES (:id_tweets, :tag)
                ON CONFLICT DO NOTHING
            """)
            connection.execute(sql, {
                'id_tweets': tweet['id'],
                'tag': tag,
            })

        # media
        media = get_media_list(tweet)
        for medium in media:
            media_url = remove_nulls(medium.get('media_url'))
            media_type = remove_nulls(medium.get('type'))

            if media_url is None:
                continue

            if schema_type == 'normalized':
                id_urls = get_id_urls(connection, media_url)
                sql = sqlalchemy.sql.text("""
                    INSERT INTO tweet_media (id_tweets, id_urls, type)
                    VALUES (:id_tweets, :id_urls, :type)
                    ON CONFLICT DO NOTHING
                """)
                connection.execute(sql, {
                    'id_tweets': tweet['id'],
                    'id_urls': id_urls,
                    'type': media_type,
                })
            else:
                sql = sqlalchemy.sql.text("""
                    INSERT INTO tweet_media (id_tweets, url, type)
                    VALUES (:id_tweets, :url, :type)
                    ON CONFLICT DO NOTHING
                """)
                connection.execute(sql, {
                    'id_tweets': tweet['id'],
                    'url': media_url,
                    'type': media_type,
                })


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--inputs', nargs='+', required=True)
    parser.add_argument('--print_every', type=int, default=10000)
    args = parser.parse_args()

    engine = sqlalchemy.create_engine(
        args.db,
        connect_args={'application_name': 'load_tweets.py'}
    )
    connection = engine.connect()

    schema_type = detect_schema(connection)
    print(datetime.datetime.now(), 'schema_type=', schema_type)

    # reverse sort reduces repeated user updates in the reference repo
    for filename in sorted(args.inputs, reverse=True):
        print(filename)
        with zipfile.ZipFile(filename, 'r') as archive:
            for subfilename in sorted(archive.namelist(), reverse=True):
                with io.TextIOWrapper(archive.open(subfilename)) as f:
                    for i, line in enumerate(f):
                        tweet = json.loads(line)
                        insert_tweet(connection, tweet, schema_type)

                        if i % args.print_every == 0:
                            print(f"{filename} - i= {i} id= {tweet['id']}")
