"""Flask server for Codenames"""
# pylint: disable=C0103

import eventlet
import logging
import pickle
import redis
import json
import os
import gc
from datetime import timedelta
from sys import getsizeof
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, join_room, leave_room, send, emit
from datetime import datetime, timedelta
from functools import reduce
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

from dotenv import load_dotenv
load_dotenv()

# attempt a relative import
try:
    from .codenames import game
except (ImportError, ValueError):
    from codenames import game

# init sentry
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FlaskIntegration()]
    )

app = Flask(__name__)
socketio = SocketIO(app)
app.secret_key = os.getenv("SECRET_KEY", "")

# set up logging
# if not app.debug:
    # gunicorn_logger = logging.getLogger('gunicorn.error')
    # app.logger.handlers = gunicorn_logger.handlers
    # app.logger.setLevel(gunicorn_logger.level)

db = redis.Redis(host='redis', port=6379, db=0)
REDIS_TTL_S = 60

def delete_room(gid):
    del ROOMS[gid]

def is_stale(room):
    """Stale rooms are older than 6 hours, or have gone 20 minutes less than 5 minutes of total playtime"""
    return (((datetime.now() - room.date_modified).total_seconds() >= (60*60*6)) or
        ((datetime.now() - room.date_modified).total_seconds() >= (60*20) and
        room.playtime() <= 5))

def prune():
    """Prune rooms stale for more than 6 hours"""
    if ROOMS:
        rooms = ROOMS.copy()
        for key in rooms.keys():
            if is_stale(ROOMS[key]):
                delete_room(key)
        del rooms
        gc.collect()

@app.route('/debug-sentry')
def trigger_error():
    division_by_zero = 1 / 0

@app.route('/stats')
def stats():
    """display room stats"""
    resp = {
        "total": len(ROOMS.keys()),
        "bytes_used": getsizeof(ROOMS)
    }
    if 'rooms' in request.args:
        if ROOMS:
            resp["rooms"] = sorted([ v.to_json() for v in ROOMS.values() ], key=lambda k: k.get('date_modified'), reverse=True)
        else:
            resp["rooms"] = None
    return jsonify(resp)

@socketio.on('create')
def on_create(data):
    """Create a game lobby"""
    # username = data['username']
    # create the game
    # handle custom wordbanks
    if data['dictionaryOptions']['useCustom']:
        gm = game.Info(
            size=data['size'],
            teams=data['teams'],
            wordbank=data['dictionaryOptions']['customWordbank'])
    # dict mixer
    elif data['dictionaryOptions']['mix']:
        gm = game.Info(
            size=data['size'],
            teams=data['teams'],
            mix=data['dictionaryOptions']['mixPercentages'])

    # handle standard single dictionary
    else:
        gm = game.Info(
            size=data['size'],
            teams=data['teams'],
            dictionary=data['dictionaryOptions']['dictionaries'])

    room = gm.game_id
    # write room to redis
    db.setex(room, REDIS_TTL_S, pickle.dumps(gm))

    join_room(room)
    # rooms[room].add_player(username)
    emit('join_room', {'room': room})
86400
@app.route('/test')
def test():
    86384
    ttl = db.ttl('VCFOG')
    return jsonify({
        "ttl": ttl,
        "ttl_m": ttl/60,
    })

@socketio.on('join')
def on_join(data):
    """Join a game lobby"""
    # username = data['username']
    room = data['room']
    game = get_game(room)

    if game:
        # add player and rebroadcast game object
        # rooms[room].add_player(username)
        join_room(room)
        send(game.to_json(), room=room)

@socketio.on('flip_card')
def on_flip_card(data):
    """flip card and rebroadcast game object"""
    room = data['room']
    game = get_game(room)
    game.flip_card(data['card'])
    db.setex(room, REDIS_TTL_S, pickle.dumps(game))
    send(game.to_json(), room=room)

@socketio.on('regenerate')
def on_regenerate(data):
    """regenerate the words list"""
    room = data['room']
    game = get_game(room)
    game.generate_board(data.get('newGame', False))
    db.setex(room, REDIS_TTL_S, pickle.dumps(game))
    send(game.to_json(), room=room)

@socketio.on('list_dictionaries')
def list_dictionaries():
    """send a list of dictionary names"""
    # send dict list to client
    emit('list_dictionaries', {'dictionaries': list(game.DICTIONARIES.keys())})

def get_game(room):
    game = db.get(room)
    if game:
        return pickle.loads(game)
    else:
        emit('error', {'error': 'Unable to join room ['+ room +']. Room does not exist.'})
        return None

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True)
