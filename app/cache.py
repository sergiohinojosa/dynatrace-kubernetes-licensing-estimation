import os
from flask import session
from flask_caching import Cache
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})


def get_init_session_id():
    if 'uid' in session:
        return session['uid']
    else:
        uid = os.urandom(12)
        session['uid'] = uid
    return uid


def get_user_cache_from_session():
    uid = get_init_session_id()
    return cache.get(uid)


def set_user_cache(estimate):
    uid = estimate.uid
    print('Setting cache for ' + str(uid) + " and " + str(estimate)  )
    cache.set(uid, estimate)