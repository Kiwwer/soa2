import helper
from flask import Flask, abort, request
from datetime import datetime
import re

app = Flask(__name__)

@app.route('/restapp/api/v1.0/users/<int:ucid>', methods=['GET'])
def get_user(ucid):
    response = helper.get_user(ucid)

    if response is None:
        abort(404)
    
    return response

@app.route('/restapp/api/v1.0/users', methods=['GET'])
def get_all_users():
    return helper.get_all_users()

@app.route('/restapp/api/v1.0/users', methods=['POST'])
def add_user():
    
    if not request.json:
        abort(400)
    if not 'nickname' in request.json:
        abort(400)
    if not 'avatar_filepath' in request.json:
        abort(400)
    if not 'gender' in request.json:
        abort(400)
    if not 'email' in request.json:
        abort(400)
    
    nickname = request.get_json()['nickname']
    avatar = request.get_json()['avatar_filepath']
    gender = request.get_json()['gender']
    email = request.get_json()['email']
    response = helper.add_to_list(nickname, avatar, gender, email)
    if response is None:
        abort(400)
    return response

@app.route('/restapp/api/v1.0/users/<int:ucid>', methods=['PUT'])
def update_user(ucid):
    response = helper.get_user(ucid)
    if response is None:
        abort(404)

    if not request.json:
        abort(400)
    if not 'nickname' in request.json:
        abort(400)
    if not 'avatar_filepath' in request.json:
        abort(400)
    if not 'gender' in request.json:
        abort(400)
    if not 'email' in request.json:
        abort(400)
    
    response = helper.update_user(ucid, request.get_json()['nickname'], request.get_json()['avatar_filepath'], request.get_json()['gender'], request.get_json()['email'])

    if response is None:
        abort(400)
    return response

@app.route('/restapp/api/v1.0/users/<int:ucid>', methods = ['DELETE'])
def delete_task(ucid):
    response = helper.get_user(ucid)
    if response is None:
        abort(404)

    response = helper.remove_user(ucid)

    return response
