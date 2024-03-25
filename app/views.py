from flask import Flask, render_template, redirect, url_for, request, session, abort, flash

from app import app
from estimate import *

@app.route('/')
def index():
    if not session.get('logged_in'):
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
    if request.method == 'POST':
        session['tenant_url'] = request.form['tenant_url']
        session['api_token'] = request.form['api_token']
        
        session['logged_in'] = True
        
    else:
        session['logged_in'] = True    
        estimate_costs()
        flash('Successful login.')
        return redirect(url_for('index'))
    return render_template('estimate.html', error=error)

@app.route("/logout")
def logout():
    session['logged_in'] = False
    return redirect(url_for('index'))
