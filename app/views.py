import os
from app import app, Estimate, estimation
from threading import Thread
from flask import Flask, render_template, redirect, url_for, request, session, abort, flash
from .cache import *


@app.route('/')
def index():

    # Get Cache for unique session, None if not available
    estimate = get_user_cache_from_session()

    if estimate is not None :
        if estimate.estimation_running:
            print("Estimation running.. loading estimate...")
            return render_template('estimate.html', estimate=estimate)
        else:
            print("Estimation not running.. loading estimate...")
            return render_template('estimate.html', estimate=estimate)
    else:
        print("Estimation not running.. loading estimate form...")
        return render_template('estimate.html', estimate=estimate)

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/contact')
def contact():
    return render_template("contact.html")

@app.route('/estimate', methods=['GET', 'POST'])
def estimate():
    error = None
    estimate = get_user_cache_from_session()
    uid = get_init_session_id()
    
    if request.method == 'POST':
    # POST Handling
        if estimate is not None:
            if estimate.estimation_running:
                print("is already running, lets wait")
        
        start_estimation(estimate, uid)
    else:
    # GET Handling
        if estimate is None:
            print("load the view again")
            return render_template('estimate.html', error=error, estimate=estimate)
        else:
            print("ESTIMATE:")
            print(estimate.__dict__)
        
        flash('Estimation running')
        return redirect(url_for('estimate', estimate=estimate))
    
    return render_template('estimate.html', error=error, estimate=estimate)



def start_estimation(estimate, uid):

    if estimate is None:
        # Initialize from Form
        tenant_url = request.form['tenant_url']
        api_token = request.form['api_token']    
        estimate = Estimate.Estimate(tenant_url, api_token, uid)
    
    # reset values
    estimate.errors = ""
    estimate.tenant_url = request.form['tenant_url']
    estimate.api_token = request.form['api_token'] 

    # Flag for running
    estimate.estimation_running = True
    
    # Add in cache
    set_user_cache(estimate)

    # Start job
    thread = Thread(target=estimation.estimate_costs_wrapper, kwargs={'e': request.args.get('e', estimate)})
    thread.start()
    





@app.route("/logout")
def logout():

    session['logged_in'] = False
    return redirect(url_for('index'))
