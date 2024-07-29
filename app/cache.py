import logging
import os
from base64 import b64encode
from flask import session
from flask_caching import Cache

from app import Estimate
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})


def get_init_session_id():
    if 'uid' in session:
        return session['uid']
    else:
        random_bytes = os.urandom(12)
        uid = b64encode(random_bytes).decode('utf-8')
        session['uid'] = uid
    return uid


def get_init_user_cache_from_session():
    uid = get_init_session_id()
    estimate = cache.get(uid)

    if estimate is None:
        estimate = Estimate.Estimate("", "", uid)
        set_user_cache(estimate)

    set_env_vars(estimate)

    return estimate


def set_user_cache(estimate):
    uid = estimate.uid
    cache_updated = cache.set(uid, estimate)
    if cache_updated:
        logging.info("Setting cache for %s with tenant:%s ", str(uid), str(estimate.tenant_url))

def set_env_vars(estimate):
    estimate.inside_vpn = os.environ.get('INSIDE_VPN', False)
    estimate.release_version = os.environ.get('RELEASE_VERSION', "0.0")
    estimate.pod_name = os.environ.get('POD_NAME', "k8stimator-rsid-pid")
    estimate.pod_namespace = os.environ.get('POD_NAMESPACE', "namespace")
    estimate.node_name = os.environ.get('NODE_NAME', "node-name")