from app import app, Estimate, estimation
from threading import Thread
from flask import Flask, render_template, redirect, url_for, request, session, abort, flash
from .cache import cache

def is_estimation_running():
    try:
        estimate = cache.get("estimate")
        print(estimate)

    except KeyError:
        return False
    
    if estimate is not None:
        return True
        #return estimate['estimation_running']
    return False


@app.route('/')
def index():
    if not is_estimation_running():
        return render_template('estimate.html')
    else:
        return render_template("index.html")

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/contact')
def contact():
    return render_template("contact.html")

@app.route('/estimate', methods=['GET', 'POST'])
def estimate():
    error = None
    estimate = None
    
    if request.method == 'POST':

        # TODO Method to fetch all data and store it in the Session.
        # TODO Stop multiple requests, if already running stop request 
        # and load UI with something pretty. Use multithreading
        try:
            #estimate_dic = session['estimate']
            estimate = cache.get("estimate")

            #estimate = Estimate.dict2obj(estimate_dic)
        
        except KeyError:
            # No key there, lets initialize one
            # Extract in methods
            tenant_url = request.form['tenant_url']
            api_token = request.form['api_token']
            
            estimate = Estimate.Estimate(tenant_url, api_token)
          
            

        
        if estimate.estimation_running:
            print("yes, lets wait")
        else:
            print("no, so lets start one")
            # Pass it as _dict_ so it can be serializable and stored in the Session
            #session['estimate'] = estimate
            cache.add("estimate", estimate)

            #estimation.estimate_costs(estimate)
            thread = Thread(target=estimation.do_work, kwargs={'e': request.args.get('e', estimate)})
            thread.start()


    else:
        try:
            estimate = cache.get('estimate')
        except KeyError:
            # No estimation in session, do POST
            print("THIS SHOULD NOT HAPPEN")
        
        flash('Estimation running')
        return redirect(url_for('index'))
    
    return render_template('index.html', error=error)

@app.route("/logout")
def logout():

    session['logged_in'] = False
    return redirect(url_for('index'))
