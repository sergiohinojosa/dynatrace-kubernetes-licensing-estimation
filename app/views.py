import os
from app import app, Estimate, estimation
from threading import Thread
from flask import Flask, render_template, redirect, url_for, request, session, abort, flash
from .cache import *


@app.route('/')
def index():

    # Get Cache for unique session, None if not available
    estimate = get_init_user_cache_from_session()
    return render_template('index.html', estimate=estimate)

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/contact')
def contact():
    return render_template("contact.html")

@app.route('/estimate', methods=['GET', 'POST'])
def estimate():
    error = None
    estimate = get_init_user_cache_from_session()
    
    if request.method == 'POST':
    # POST Handling
        if estimate.estimation_running:
            print("Estimation is already running")
            flash('Estimation is already running')
        else:    
            start_estimation(estimate)
    else:
    # GET Handling
        return render_template('estimate.html', error=error, estimate=estimate)
    
    return render_template('estimate.html', error=error, estimate=estimate)



def start_estimation(estimate):

    # TODO Validate all Form Fields
    # reset values
    estimate.errors = ""
    estimate.tenant_url = request.form['tenant_url']
    estimate.api_token = request.form['api_token'] 
    
    estimate.ssoCSRFCookie = request.form['ssoCSRFCookie'] 
    estimate.jsessionId = request.form['jsessionId'] 
    estimate.resolution = request.form['resolution'] 
    estimate.from_timeframe = request.form['from_timeframe']
    estimate.iterations = int(request.form['iterations']) 
    estimate.days_per_iteration = int(request.form['days_per_iteration']) 


    if estimate.tenant_url == "":
                estimate.errors = "Please enter a valid Tenant url"
    

    # If no errors, kick job
    if estimate.errors == "":
        # Flag for running
        estimate.estimation_running = True
        # Start job in new Thread
        thread = Thread(target=estimation.estimate_costs_wrapper, kwargs={'e': request.args.get('e', estimate)})
        thread.start() 

    # Add in cache
    set_user_cache(estimate)
        


@app.route("/logout")
def logout():

    session['logged_in'] = False
    return redirect(url_for('index'))
