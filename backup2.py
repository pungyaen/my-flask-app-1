from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import os
from datetime import datetime, timedelta
import threading
import time
from PIL import Image, ImageDraw, ImageFont
import requests

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

    # ตรวจสอบความพร้อมของห้อง
    checkin_date = datetime.strptime(checkin, '%Y-%m-%d')
    checkout_date = datetime.strptime(checkout, '%Y-%m-%d')
    date_to_check = checkin_date

    con = sqlite3.connect('instance/reservations.db')
    cur = con.cursor()

    while date_to_check < checkout_date:
        date_str = date_to_check.strftime('%Y-%m-%d')
        cur.execute("SELECT available_rooms FROM room_availability WHERE date = ?", (date_str,))
        row = cur.fetchone()
        if row is None:
            con.close()
            return jsonify({'message': f'No room availability data for {date_str}. Please select another date.'}), 400
        available_rooms = row[0]
        if available_rooms <= 0:
            con.close()
            return jsonify({'message': f'No rooms available on {date_str}. Please select another date.'}), 400
        date_to_check += timedelta(days=1)

    # ถ้าวันที่ที่เลือกมีห้องว่างทั้งหมดก็ทำการบันทึกการจอง
    new_reservation = Reservation(name=name, phone=phone, checkin=checkin, checkout=checkout, slip=slip_filename)
    db.session.add(new_reservation)
    db.session.commit()

    # อัปเดตจำนวนห้องว่างในแต่ละวันหลังจากการจอง
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

    # ดึงข้อมูลการจองทั้งหมด
    reservations = get_reservation_data()
    # ดึงข้อมูลห้องว่างทั้งหมด
    room_availabilities = get_room_availability()
    # สร้างภาพ
    img = create_reservation_image(reservations, room_availabilities, new_reservation.id)
    save_image(img)

    # ส่งภาพผ่าน LINE
    line_token = 'ca7yuOC9DjF8FNfHZMaPRMtGORlydUUX83VqTwVoMiR'  # เปลี่ยนด้วย token ของคุณ
    send_line_image('reservation_details.jpg', line_token)

    return jsonify({'message': 'เจ้าหน้าที่ได้รับใบจองแล้ว (*การจองจะสำเร็จเมื่อแนบสลิปโอนเงินและมียอดเงินเข้าครบถ้วนแล้วเท่านั้น*)'})

@app.route('/get-room-status')
def get_room_status():
    reservations = RoomAvailability.query.all()
    events = []
    for reservation in reservations:
        if reservation.available_rooms > 0:
            events.append({
                'title': f'{reservation.available_rooms} rooms available',
                'start': reservation.date,
                'end': reservation.date,
                'overlap': False,
                'display': 'background',
                'color': '#d4edda'
            })
    return jsonify(events)

def get_reservation_data():
    con = sqlite3.connect('instance/reservations.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM reservation")
    reservations = cur.fetchall()
    con.close()
    return reservations

def get_room_availability():
    con = sqlite3.connect('instance/reservations.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM room_availability")
    room_availabilities = cur.fetchall()
    con.close()
    return room_availabilities

def create_reservation_image(reservations, room_availabilities, latest_reservation_id):
    img = Image.new('RGB', (800, 1000), color='white')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 15)
        bold_font = ImageFont.truetype("arialbd.ttf", 15)
    except IOError:
        font = ImageFont.load_default()
        bold_font = ImageFont.load_default()

    y_offset = 10
    draw.text((10, y_offset), "Reservations:", font=font, fill='black')
    y_offset += 30

    for reservation in reservations:
        idd = reservation[0]
        name = reservation[1]
        phone = reservation[2]
        checkin = reservation[3]
        checkout = reservation[4]
        slip = reservation[5]
        line = f"ID: {idd}, Name: {name}, Phone: {phone}, Check-in: {checkin}, Check-out: {checkout}, Slip: {slip}"
        if idd == latest_reservation_id:
            draw.text((10, y_offset), line, font=bold_font, fill='red')
        else:
            draw.text((10, y_offset), line, font=font, fill='black')
        y_offset += 20

    y_offset += 20
    draw.text((10, y_offset), "Room Availability:", font=font, fill='black')
    y_offset += 30

    for room in room_availabilities:
        date = room[1]
        available_rooms = room[2]
        line = f"Date: {date}, Available Rooms: {available_rooms}"
        draw.text((10, y_offset), line, font=font, fill='black')
        y_offset += 20

    return img

def save_image(img):
    img.save('reservation_details.jpg')

def send_line_image(image_path, token):
    url = 'https://notify-api.line.me/api/notify'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    message = {'message': 'รายละเอียดการจองและจำนวนห้องว่าง'}
    files = {'imageFile': open(image_path, 'rb')}
    response = requests.post(url, headers=headers, data=message, files=files)
    return response

def initialize_room_availability():
    start_date = datetime.now().date()
    end_date = start_date + timedelta(days=30)

    current_date = start_date
    while current_date <= end_date:
        day_of_week = current_date.weekday()
        if day_of_week < 5:
            available_rooms = 5
        else:
            available_rooms = 5

        date_str = current_date.strftime('%Y-%m-%d')
        room_availability = RoomAvailability(date=date_str, available_rooms=available_rooms)
        db.session.add(room_availability)
        current_date += timedelta(days=1)

    db.session.commit()

def update_room_availability():
    while True:
        try:
            con = sqlite3.connect('instance/reservations.db')
            cur = con.cursor()
            cur.execute("UPDATE room_availability SET available_rooms = 3")
            cur.execute("SELECT checkin, checkout FROM reservation")
            reservations = cur.fetchall()

            for reservation in reservations:
                checkin_date = datetime.strptime(reservation[0], '%Y-%m-%d')
                checkout_date = datetime.strptime(reservation[1], '%Y-%m-%d')
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
        except sqlite3.OperationalError as e:
            print(f"SQLite error: {e}. Retrying in 1 second...")
            time.sleep(1)
            continue

        time.sleep(30)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if RoomAvailability.query.count() == 0:
            initialize_room_availability()

        update_thread = threading.Thread(target=update_room_availability)
        update_thread.start()

    app.run(debug=True)
