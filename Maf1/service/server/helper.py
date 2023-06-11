import sqlite3
from flask import jsonify, url_for

DB_PATH = './users.db'   # Update this path accordingly

def make_public_user(row):
    new_user = {}
    for field in row.keys():
        if field == 'ucid':
            new_user['uri'] = url_for('get_user', ucid = row['ucid'], _external = True)
        else:
            new_user[field] = row[field]

    return new_user

def get_all_users():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('select * from users')
        rows = c.fetchall()
        result = jsonify( { 'users': list(map(make_public_user, rows)) } )
        return result
    except Exception as e:
        print('Error: ', e)
        return None

def get_user(ucid):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("select * from users where ucid=?;" , [ucid])
        r = c.fetchone()
        return jsonify(make_public_user(r))
    except Exception as e:
        print('Error: ', e)
    return None

def add_to_list(nickname, avatar, gender, email):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('insert into users(nickname, avatar_filepath, gender, email) values(?,?,?,?)', (nickname, avatar, gender, email))
        conn.commit()
        result = get_user(c.lastrowid)
        return result
    except Exception as e:
        print('Error: ', e)
        return None

def update_user(ucid, nickname, avatar, gender, email):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('update users set nickname=?, avatar_filepath=?, gender=?, email=? where ucid=?', (nickname, avatar, gender, email, ucid))
        conn.commit()
        result = get_user(ucid)
        return result
    except Exception as e:
        print('Error: ', e)
        return None

def remove_user(ucid):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM users WHERE ucid=?', [ucid])
        conn.commit()
        return jsonify( { 'result': True } )
    except Exception as e:
        print('Error: ', e)
        return None
