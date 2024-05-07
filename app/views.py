import os
from app import app, Estimate, estimation
from threading import Thread
from flask import Flask, render_template, redirect, url_for, request, session, abort, flash
from .cache import *

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    estimate = get_init_user_cache_from_session()
    inside_vpn = os.environ.get('INSIDE_VPN', False)
    
    if request.method == 'POST':
    # POST Handling
        if estimate.estimation_running:
            print("Estimation is already running")
            flash('Estimation is already running')
        else:    
            start_estimation(estimate)
    else:
    # GET Handling
        return render_template('index.html', error=error, estimate=estimate, inside_vpn=inside_vpn)
    
    return render_template('index.html', error=error, estimate=estimate, inside_vpn=inside_vpn)

@app.route('/doc')
def about():
    estimate = get_init_user_cache_from_session()
    return render_template("doc.html",  estimate=estimate)

@app.route('/help')
def contact():
    estimate = get_init_user_cache_from_session()
    return render_template("help.html",  estimate=estimate)

@app.route('/show_cache')
def show_cache():

    # Get Cache for unique session, None if not available
    estimate = get_init_user_cache_from_session()
    return render_template('show_cache.html', estimate=estimate)

def start_estimation(estimate):

    # Reset Error & Console
    estimate.errors = ""
    estimate.console = ""

    # Reset previous values (if any)
    estimate.t_pod_h = 0
    estimate.t_gib_h = 0
    estimate.t_instances = 0
    estimate.t_shortliving_instances = 0

    estimate.tenant_url = request.form['tenant_url']
    estimate.api_token = request.form['api_token'] 
    
    estimate.ssoCSRFCookie = request.form['ssoCSRFCookie'] 
    estimate.jsessionId = request.form['jsessionId'] 
    estimate.resolution = request.form['resolution'] 
    estimate.from_timeframe = request.form['from_timeframe']
    estimate.iterations = int(request.form['iterations']) 
    estimate.days_per_iteration = int(request.form['days_per_iteration'])

    try:
        # Validate all fields, on error we raise
        estimate.validate_form_fields()

        # Flag for running
        estimate.estimation_running = True

        # Add in cache
        set_user_cache(estimate)
        
        # Start Job in new Thread
        thread = Thread(target=estimation.estimate_costs_wrapper, kwargs={'e': request.args.get('e', estimate)})
        thread.start()

    except SyntaxWarning as war:
        estimate.estimation_running = False
        estimate.errors = str(war)
        logging.error("There was a %s error: %s", type(war), war)
    return
         

        

@app.route("/logout")
def logout():

    session['logged_in'] = False
    return redirect(url_for('index'))
