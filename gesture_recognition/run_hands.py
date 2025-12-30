# Copyright 2023 The MediaPipe Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Main script to run hand gesture recognition and hand landmark detection."""

import argparse
import sys
import time

import socket, json

import cv2
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2

HOST = '127.0.0.1'
PORT = 3105

upload_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
upload_client.connect((HOST, PORT))


def send_cin(con, msg):
    cin = {'ctname': con, 'con': msg}
    msg = (json.dumps(cin) + '<EOF>')
    upload_client.sendall(msg.encode('utf-8'))

    # 너무 많은 로그는 버벅임의 원인이 될 수 있음
    # 필요하면 아래 주석 풀어서 디버깅용으로만 사용
    # print(f"send {msg} to {con}")


mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Global variables to calculate FPS and store detection results
COUNTER, FPS = 0, 0
START_TIME = time.time()
DETECTION_RESULT = [None]


def run(model: str, num_hands: int,
        min_hand_detection_confidence: float,
        min_hand_presence_confidence: float, min_tracking_confidence: float,
        camera_id: int, width: int, height: int, task: str) -> None:
    """Continuously run inference on images acquired from the camera."""

    # Start capturing video input from the camera
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # 카메라 FPS를 낮춰서 프레임이 너무 많이 들어오는 것 방지 (선택)
    cap.set(cv2.CAP_PROP_FPS, 15)
    
    # 카메라 초기화 대기 및 웜업
    print("[INFO] 카메라 초기화 중...")
    import time as wait_time
    wait_time.sleep(1)
    
    # 카메라 웜업 -설정 때문에 처음 몇 프레임은 버림
    print("[INFO] 카메라 웜업 중...")
    for _ in range(5):
        cap.read()
        wait_time.sleep(0.1)
    
    print("[SUCCESS] 카메라 준비 완료!")

    temp_data = {}
    last_send_time = {}
    cooldown_duration = 2  # seconds, adjust as needed

    # Visualization parameters
    row_size = 50  # pixels
    left_margin = 24  # pixels
    text_color = (255, 255, 255)  # white
    font_size = 1
    font_thickness = 1
    fps_avg_frame_count = 10

    def save_result(result, unused_output_image, timestamp_ms):
        global FPS, COUNTER, START_TIME, DETECTION_RESULT

        if COUNTER % fps_avg_frame_count == 0:
            FPS = fps_avg_frame_count / (time.time() - START_TIME)
            START_TIME = time.time()

        DETECTION_RESULT[0] = result
        COUNTER += 1

    # Initialize the MediaPipe hand task.
    base_options = python.BaseOptions(model_asset_path=model)
    if task == 'gesture_recognizer':
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            result_callback=save_result)
        detector = vision.GestureRecognizer.create_from_options(options)
        detect_async_fn = detector.recognize_async
    elif task == 'hand_landmarker':
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            result_callback=save_result)
        detector = vision.HandLandmarker.create_from_options(options)
        detect_async_fn = detector.detect_async
    else:
        sys.exit(f"Invalid task: {task}")

    # 프레임 스킵용 카운터 (모든 프레임을 다 인퍼런스하지 않기 위함)
    frame_counter = 0
    skip_interval = 2  # 2면 2프레임마다 한 번만 인퍼런스, 필요하면 3으로 올려봐도 됨

    # Continuously capture images from the camera and run inference
    while cap.isOpened():
        success, image = cap.read()
        if not success:
            sys.exit('ERROR: Unable to read from webcam. Please verify your webcam settings.')

        image = cv2.flip(image, 1)
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        frame_counter += 1
        # 🔴 모든 프레임을 보내지 않고, 일부만 MediaPipe로 보냄 → 큐가 덜 쌓임
        if frame_counter % skip_interval == 0:
            detect_async_fn(mp_image, time.time_ns() // 1_000_000)

        current_frame = image
        fps_text = 'FPS = {:.1f}'.format(FPS)
        text_location = (left_margin, row_size)
        cv2.putText(current_frame, fps_text, text_location, cv2.FONT_HERSHEY_DUPLEX,
                    font_size, text_color, font_thickness, cv2.LINE_AA)

        if DETECTION_RESULT[0]:
            # Draw landmarks and handedness (common to both tasks)
            for i, hand_landmarks in enumerate(DETECTION_RESULT[0].hand_landmarks):
                # Draw landmarks
                hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
                hand_landmarks_proto.landmark.extend([
                    landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z)
                    for landmark in hand_landmarks
                ])
                mp_drawing.draw_landmarks(
                    current_frame,
                    hand_landmarks_proto,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style())

                # Get the top left corner of the detected hand's bounding box.
                height, width, _ = current_frame.shape
                x_coordinates = [landmark.x for landmark in hand_landmarks]
                y_coordinates = [landmark.y for landmark in hand_landmarks]
                text_x = int(min(x_coordinates) * width)
                text_y = int(min(y_coordinates) * height) - 10  # Margin

            # Draw gestures (only for gesture_recognizer)
            if task == 'gesture_recognizer' and DETECTION_RESULT[0].gestures:
                for i, gesture in enumerate(DETECTION_RESULT[0].gestures):
                    # Find hand landmarks for this gesture
                    hand_landmarks = DETECTION_RESULT[0].hand_landmarks[i]
                    x_coordinates = [landmark.x for landmark in hand_landmarks]
                    y_coordinates = [landmark.y for landmark in hand_landmarks]
                    text_x = int(min(x_coordinates) * width)
                    text_y = int(min(y_coordinates) * height) - 40  # Margin below handedness

                    # 안전하게 handedness 가져오기
                    if i < len(DETECTION_RESULT[0].handedness) and DETECTION_RESULT[0].handedness[i]:
                        handedness_category = DETECTION_RESULT[0].handedness[i][0].category_name
                    else:
                        handedness_category = "Unknown"
                    
                    gesture_category = gesture[0].category_name
                    gesture_score = round(gesture[0].score, 2)

                    result_text = f'{handedness_category}: {gesture_category} ({gesture_score})'
                    cv2.putText(current_frame, result_text, (text_x, text_y),
                                cv2.FONT_HERSHEY_DUPLEX, font_size,
                                text_color, font_thickness, cv2.LINE_AA)

                    # Send gesture data to the server
                    current_gesture = f"{handedness_category}_{gesture_category}"
                    last_gesture = temp_data.get(i)

                    if gesture_category != "None" and current_gesture != last_gesture:
                        current_time = time.time()
                        if i not in last_send_time or (current_time - last_send_time.get(i, 0)) > cooldown_duration:
                            send_cin("hand_gestures", current_gesture)
                            last_send_time[i] = current_time

                    temp_data[i] = current_gesture

        cv2.imshow('Hand Tracking', current_frame)

        if cv2.waitKey(1) == 27:
            break

    detector.close()
    cap.release()
    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--task',
        help='The hand tracking task to run.',
        required=False,
        choices=['gesture_recognizer', 'hand_landmarker'],
        default='gesture_recognizer')
    parser.add_argument(
        '--model',
        help='Name of the model bundle. If not provided, the default for the selected task will be used.',
        required=False,
        default=None)
    parser.add_argument(
        '--numHands',
        help='Max number of hands that can be detected.',
        required=False,
        default=2)
    parser.add_argument(
        '--minHandDetectionConfidence',
        help='The minimum confidence score for hand detection to be considered successful.',
        required=False,
        default=0.5)
    parser.add_argument(
        '--minHandPresenceConfidence',
        help='The minimum confidence score of hand presence score in the hand landmark detection.',
        required=False,
        default=0.5)
    parser.add_argument(
        '--minTrackingConfidence',
        help='The minimum confidence score for the hand tracking to be considered successful.',
        required=False,
        default=0.5)
    parser.add_argument('--cameraId', help='Id of camera.', required=False, default=0)
    # 🔴 해상도 다시 줄이기 (1280x960 → 640x480)
    parser.add_argument('--frameWidth', help='Width of frame to capture from camera.', required=False, default=640)
    parser.add_argument('--frameHeight', help='Height of frame to capture from camera.', required=False, default=480)
    args = parser.parse_args()

    model_path = args.model
    if model_path is None:
        if args.task == 'gesture_recognizer':
            model_path = 'gesture_recognizer.task'
        else:  # hand_landmarker
            model_path = 'hand_landmarker.task'

    run(model_path, int(args.numHands), float(args.minHandDetectionConfidence),
        float(args.minHandPresenceConfidence), float(args.minTrackingConfidence),
        int(args.cameraId), args.frameWidth, args.frameHeight, args.task)


if __name__ == '__main__':
    main()
