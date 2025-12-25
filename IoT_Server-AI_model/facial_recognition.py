import socket, json

HOST = '127.0.0.1'
PORT = 3105

upload_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
upload_client.connect((HOST, PORT))

import argparse
import os
import sys
import time

import cv2
import numpy as np
from tensorflow.keras.layers import (Conv2D, Dense, Dropout, Flatten, MaxPooling2D)
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Flatten
from tensorflow.keras.layers import Conv2D
from tensorflow.keras.layers import MaxPooling2D
import os
import sys
import subprocess

from tensorflow.keras.models import load_model

temp_data = ''

def send_cin(con,msg) :

    cin = {'ctname': con, 'con': msg}
    msg = (json.dumps(cin) + '<EOF>')
    upload_client.sendall(msg.encode('utf-8'))

    print (f"send {msg} to {con}")

if sys.platform == 'linux':
    from gpiozero import CPUTemperature

# input arg parsing
parser = argparse.ArgumentParser()
parser.add_argument('-f', '--fullscreen',
                    help='Display window in full screen', action='store_true')
parser.add_argument(
    '-d', '--debug', help='Display debug info', action='store_true')
parser.add_argument(
    '-fl', '--flip', help='Flip incoming video signal', action='store_true')
args = parser.parse_args()

model = load_model('my_model.h5')

cv2.ocl.setUseOpenCL(False)

emotion_dict = {0: "Angry", 1: "Disgusted", 2: "Fearful",
                3: "Happy", 4: "Sad", 5: "Surprise", 6: "Neutral"}

def get_gpu_temp():
    temp = subprocess.check_output(['vcgencmd measure_temp | egrep -o \'[0-9]*\.[0-9]*\''],
                                    shell=True, universal_newlines=True)
    return str(float(temp))

# start the webcam feed
cap = cv2.VideoCapture(0)
zoom_scale = 3
while True:
    # time for fps
    start_time = time.time()

    # Find haar cascade to draw bounding box around face
    ret, frame = cap.read()
    frame = cv2.flip(frame, 1)
    
    # if args.flip:
    #     frame = cv2.flip(frame, 1)
    if not ret:
        break

    height, width, _ = frame.shape
    centerX, centerY = int(height / 2), int(width / 2)
    radiusX, radiusY = int(height / (2 * zoom_scale)), int(width / (2 * zoom_scale))

    minX, maxX = centerX - radiusX, centerX + radiusX
    minY, maxY = centerY - radiusY, centerY + radiusY

    cropped = frame[minX:maxX, minY:maxY]
    resized_cropped = cv2.resize(cropped, (width, height))


    facecasc = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = facecasc.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    max_area = 0
    x_max = y_max = w_max = h_max = 0
    for (x, y, w, h) in faces:
        if w*h > max_area:
            x_max, y_max, w_max, h_max = x, y, w, h
            max_area = w*h

    if max_area > 0:
        cv2.rectangle(frame, (x_max, y_max-50), (x_max+w_max, y_max+h_max+10), (255, 0, 0), 2)
        roi_gray = gray[y_max:y_max + h_max, x_max:x_max + w_max]
        cropped_img = np.expand_dims(np.expand_dims(cv2.resize(roi_gray, (48, 48)), -1), 0)
        prediction = model.predict(cropped_img)
        maxindex = int(np.argmax(prediction))
        emotion_label = emotion_dict[maxindex]

        cv2.putText(frame, emotion_label, (x_max+20, y_max-60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
        
        if emotion_label != temp_data:
            temp_data = str(emotion_label)
            send_cin("emotion", str(emotion_label))
    
    cv2.imshow("Frame", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
