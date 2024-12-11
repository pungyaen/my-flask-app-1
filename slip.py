from flask import Blueprint, request, flash, redirect, render_template
from PIL import Image
import pytesseract
import os

slip_blueprint = Blueprint('slip', __name__)

@slip_blueprint.route('/submit_reservation', methods=['POST'])
def submit_reservation():
    # ตรวจสอบว่ามีไฟล์อัปโหลดมา
    if 'slip' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['slip']

    # ตรวจสอบว่ามีการเลือกไฟล์
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if file:
        # บันทึกไฟล์ที่อัปโหลดมา
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)

        # ใช้ OCR ตรวจสอบตัวเลขในภาพ
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)

        if '450' in text:
            # ถ้ามีตัวเลข 450 ในภาพ ให้ดำเนินการต่อ
            flash('Slip is valid.')
            # เพิ่มโค้ดสำหรับการบันทึกการจองที่นี่
        else:
            # ถ้าไม่มีตัวเลข 450 ในภาพ ให้แจ้งผู้ใช้
            flash('Invalid slip. The uploaded slip does not contain the number 450.')
            os.remove(file_path)
            return redirect(request.url)

    return render_template('submit_reservation.html')
