from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import os
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    checkin = db.Column(db.String(10), nullable=False)
    checkout = db.Column(db.String(10), nullable=False)
    slip = db.Column(db.String(100), nullable=False)


class RoomAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, unique=True)
    available_rooms = db.Column(db.Integer, nullable=False)


@app.route('/')
def hotel_informaion():
    return render_template('hotel_informaion.html')

@app.route('/status_room')
def status_room():
    return render_template('status_room.html')

@app.route('/reservation_form')
def reservation_form():
    return render_template('reservation_form.html')

@app.route('/submit-reservation', methods=['POST'])
def submit_reservation():
    name = request.form['name']
    phone = request.form['phone']
    checkin = request.form['checkin']
    checkout = request.form['checkout']
    slip = request.files['slip']

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    slip_filename = os.path.join(app.config['UPLOAD_FOLDER'], slip.filename)
    slip.save(slip_filename)

    new_reservation = Reservation(name=name, phone=phone, checkin=checkin, checkout=checkout, slip=slip_filename)
    db.session.add(new_reservation)
    db.session.commit()

    # อัปเดตจำนวนห้องว่างในแต่ละวันหลังจากการจอง
    con = sqlite3.connect('instance/reservations.db')
    cur = con.cursor()

    checkin_date = datetime.strptime(checkin, '%Y-%m-%d')
    checkout_date = datetime.strptime(checkout, '%Y-%m-%d')
    date_to_update = checkin_date

    while date_to_update < checkout_date:
        date_str = date_to_update.strftime('%Y-%m-%d')
        cur.execute("SELECT available_rooms FROM room_availability WHERE date = ?", (date_str,))
        available_rooms = cur.fetchone()[0]
        available_rooms -= 1
        cur.execute("UPDATE room_availability SET available_rooms = ? WHERE date = ?", (available_rooms, date_str))
        date_to_update += timedelta(days=1)

    con.commit()
    con.close()

    return jsonify({'message': 'Reservation successful!'})



if __name__ == '__main__':

    app.run(debug=True)
