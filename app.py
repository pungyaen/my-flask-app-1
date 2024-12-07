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

if __name__ == '__main__':

    app.run(debug=True)
