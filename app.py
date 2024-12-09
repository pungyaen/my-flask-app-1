from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import os
from datetime import datetime, timedelta
import threading
import time
from PIL import Image, ImageDraw, ImageFont
import requests
import base64

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

    # ดึงวันที่และเวลาในรูปแบบที่ต้องการ เช่น 'YYYY-MM-DD_HH-MM-SS'
    current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    # ใช้ชื่อไฟล์ใหม่ที่สร้างจากวันที่และเวลา
    slip_filename = os.path.join(app.config['UPLOAD_FOLDER'], f"{current_time}_{slip.filename}")

    # บันทึกไฟล์ที่อัพโหลดด้วยชื่อใหม่
    slip.save(slip_filename)

    # ส่งภาพผ่าน LINE
    line_token = 'ca7yuOC9DjF8FNfHZMaPRMtGORlydUUX83VqTwVoMiR'  # เปลี่ยนด้วย token ของคุณ
    send_line_image_2(slip_filename, line_token)

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

    return jsonify({'message': 'reservation form was sent (*booking completed when full transaction completed only*)'})

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

def send_line_image_2(image_path, token):
    url = 'https://notify-api.line.me/api/notify'
    headers = {
        'Authorization': f'Bearer {token}',
    }

    message = {'message': 'มีการอัปโหลดสลิปโอนเงินใหม่'}
    files = {'imageFile': open(image_path, 'rb')}

    # ส่ง POST request ไปยัง LINE Notify
    response = requests.post(url, headers=headers, data=message, files=files)

    # ปิดไฟล์หลังจากส่ง
    files['imageFile'].close()

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

import requests
import base64

file_path = "instance/reservations.db"
repo = "pungyaen/my-flask-app-1"
path_in_repo = "instance/reservations.db"
commit_message = "Update reservations.db"
branch = "master"  # หรือ master
token = "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"  # เปลี่ยนเป็นโทเคนของคุณ



def upload_file_to_github(file_path, repo, path_in_repo, commit_message, branch, token):
    # อ่านไฟล์
    with open(file_path, "rb") as file:
        content = file.read()
        content_b64 = base64.b64encode(content).decode("utf-8")

    # URL สำหรับ API GitHub
    url = f"https://api.github.com/repos/{repo}/contents/{path_in_repo}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # ตรวจสอบว่าไฟล์มีอยู่แล้วหรือไม่
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        sha = response.json()["sha"]
    else:
        sha = None

    # ข้อมูลที่จะส่ง
    data = {
        "message": commit_message,
        "content": content_b64,
        "branch": branch
    }

    if sha:
        data["sha"] = sha  # ถ้ามีไฟล์ที่มีอยู่แล้วให้ใส่ sha ของไฟล์นั้น

    # ส่งคำขอ PUT
    response = requests.put(url, json=data, headers=headers)

    if response.status_code in [200, 201]:
        print(f"File '{path_in_repo}' successfully uploaded to GitHub.")
    else:
        print(f"Failed to upload file to GitHub: {response.status_code}")
        print(response.json())

upload_file_to_github(file_path, repo, path_in_repo, commit_message, branch, token)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if RoomAvailability.query.count() == 0:
            initialize_room_availability()

        update_thread = threading.Thread(target=update_room_availability)
        update_thread.start()

    app.run(debug=True)

