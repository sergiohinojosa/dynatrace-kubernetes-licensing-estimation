import logging
import os
from flask import session
from flask_caching import Cache

from app import Estimate
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})


def get_init_session_id():
    if 'uid' in session:
        return session['uid']
    else:
        uid = os.urandom(12)
        session['uid'] = uid
    return uid


def get_init_user_cache_from_session():
    uid = get_init_session_id()
    estimate = cache.get(uid)

    if estimate is None:
        estimate = Estimate.Estimate("", "", uid)
        set_user_cache(estimate)

    return estimate


def set_user_cache(estimate):
    uid = estimate.uid
    logging.info("Setting cache for %s  and %s ", str(uid), str(estimate))
    cache.set(uid, estimate)