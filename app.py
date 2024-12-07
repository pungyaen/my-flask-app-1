from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import os
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)


@app.route('/')
def hotel_informaion():
    return render_template('hotel_informaion.html')

@app.route('/status_room')
def status_room():
    return render_template('status_room.html')

@app.route('/reservation_form')
def reservation_form():
    return render_template('reservation_form.html')

if __name__ == '__main__':

    app.run(debug=True)
