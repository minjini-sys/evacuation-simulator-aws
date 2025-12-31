# Copyright 2023 The MediaPipe Authors. All Rights Reserved.
# Modified by Gemini-CLI to use MQTT for publishing gestures.

import argparse
import sys
import time
import json
import os
from dotenv import load_dotenv
import paho.mqtt.client as mqtt # Using paho-mqtt for sync MQTT client

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2

# --- MQTT 諛?oneM2M ?ㅼ젙 ---
# .env ?뚯씪?먯꽌 Mobius 愿???뺣낫瑜?媛?몄샃?덈떎.
# .env ?뚯씪? ???ㅽ겕由쏀듃???곸쐞 ?대뜑???꾨줈?앺듃 猷⑦듃???덈떎怨?媛?뺥빀?덈떎.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MOBIUS_CSE = os.getenv("MOBIUS_CSE", "mobius-yt")

# ??AE(Application Entity)???대쫫. Server_MQTT.py媛 援щ룆?섎뒗 ??곴낵 愿?⑤맗?덈떎.
# .env??AE_NAME_GESTURE ?깆쑝濡??뺤쓽?섎뒗 寃껋쓣 異붿쿇?⑸땲??
AE_NAME = os.getenv("AE_NAME_GESTURE", "ae-gesture") 
# ?쒖뒪泥??곗씠?곕? ??ν븷 而⑦뀒?대꼫(CNT) ?대쫫
CNT_NAME = "hand_gestures"

# oneM2M ?붿껌??蹂대궪 MQTT ?좏뵿
# ?뺤떇: /oneM2M/req/{originator}/{to}/json
MQTT_REQ_TOPIC = f"/oneM2M/req/{AE_NAME}/{MOBIUS_CSE}/json"

# MQTT ?대씪?댁뼵???ㅼ젙
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print("[MQTT] 釉뚮줈而ㅼ뿉 ?깃났?곸쑝濡??곌껐?섏뿀?듬땲??", file=sys.stderr)
    else:
        print(f"[MQTT] 釉뚮줈而??곌껐 ?ㅽ뙣, 肄붾뱶: {rc}", file=sys.stderr)

mqtt_client.on_connect = on_connect
try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start() # 諛깃렇?쇱슫?쒖뿉???ㅽ듃?뚰겕 猷⑦봽 泥섎━
except Exception as e:
    print(f"[MQTT] MQTT ?곌껐???ㅽ뙣?덉뒿?덈떎: {e}", file=sys.stderr)
    sys.exit(1)


def send_cin(container_name: str, gesture_data: str):
    """
    oneM2M??ContentInstance(cin)瑜??앹꽦?섎뒗 MQTT 硫붿떆吏瑜?寃뚯떆(Publish)?⑸땲??
    """
    global mqtt_client, AE_NAME, MOBIUS_CSE

    # oneM2M ContentInstance 생성 요청 페이로드 (JSON)
    payload = {
        "m2m:rqp": {
            "op": 1,  # 1 = Create
            "to": f"/{MOBIUS_CSE}/{AE_NAME}/{container_name}", # 대상 리소스 경로
            "fr": AE_NAME, # 요청자 (Originator)
            "rqi": f"rqi-{int(time.time())}", # 고유한 요청 ID
            "ty": 4,  # 4 = ContentInstance
            "pc": {
                "m2m:cin": {
                    "con": gesture_data # 실제 데이터
                }
            }
        }
    }
    
    # MQTT ?좏뵿?쇰줈 JSON ?섏씠濡쒕뱶 寃뚯떆
    mqtt_client.publish(MQTT_REQ_TOPIC, json.dumps(payload))
    # print(f"Published to {MQTT_REQ_TOPIC}: {gesture_data}", file=sys.stderr)


# --- 湲곗〈 run_hands.py 濡쒖쭅 (socket 遺遺??쒖쇅) ---

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

COUNTER, FPS = 0, 0
START_TIME = time.time()
DETECTION_RESULT = [None]

def run(model: str, num_hands: int,
        min_hand_detection_confidence: float,
        min_hand_presence_confidence: float, min_tracking_confidence: float,
        camera_id: int, width: int, height: int, task: str) -> None:
    # (湲곗〈 run_hands.py??run ?⑥닔? 嫄곗쓽 ?숈씪)
    # (send_cin ?몄텧 遺遺꾨쭔 蹂寃쎈맖)
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, 15)
    
    print("[INFO] 移대찓??珥덇린???꾨즺.", file=sys.stderr)
    time.sleep(1.0)

    temp_data = {}
    last_send_time = {}
    cooldown_duration = 2

    def save_result(result, unused_output_image, timestamp_ms):
        global FPS, COUNTER, START_TIME, DETECTION_RESULT
        if COUNTER % 10 == 0:
            FPS = 10 / (time.time() - START_TIME)
            START_TIME = time.time()
        DETECTION_RESULT[0] = result
        COUNTER += 1

    base_options = python.BaseOptions(model_asset_path=model)
    if task == 'gesture_recognizer':
        options = vision.GestureRecognizerOptions(
            base_options=base_options, running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=num_hands, min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence, result_callback=save_result)
        detector = vision.GestureRecognizer.create_from_options(options)
    else: # hand_landmarker
        options = vision.HandLandmarkerOptions(
            base_options=base_options, running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=num_hands, min_hand_detection_confidence=min_hand_detection_confidence,
            min_hand_presence_confidence=min_hand_presence_confidence,
            min_tracking_confidence=min_tracking_confidence, result_callback=save_result)
        detector = vision.HandLandmarker.create_from_options(options)

    detect_async_fn = detector.recognize_async if task == 'gesture_recognizer' else detector.detect_async

    frame_counter = 0
    skip_interval = 2

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            break

        image = cv2.flip(image, 1)
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        if frame_counter % skip_interval == 0:
            detect_async_fn(mp_image, time.time_ns() // 1_000_000)

        current_frame = image
        # ... (湲곗〈???붾㈃??洹몃━??濡쒖쭅? ?숈씪)

        if DETECTION_RESULT[0] and task == 'gesture_recognizer' and DETECTION_RESULT[0].gestures:
            for i, gesture in enumerate(DETECTION_RESULT[0].gestures):
                # ...
                if i < len(DETECTION_RESULT[0].handedness) and DETECTION_RESULT[0].handedness[i]:
                    handedness_category = DETECTION_RESULT[0].handedness[i][0].category_name
                else:
                    handedness_category = "Unknown"
                
                gesture_category = gesture[0].category_name
                current_gesture = f"{handedness_category}_{gesture_category}"
                last_gesture = temp_data.get(i)

                if gesture_category != "None" and current_gesture != last_gesture:
                    current_time = time.time()
                    if i not in last_send_time or (current_time - last_send_time.get(i, 0)) > cooldown_duration:
                        # ?뵶 ?듭떖 蹂寃? ?뚯폆 ???MQTT濡??쒖뒪泥??곗씠???꾩넚
                        send_cin(CNT_NAME, current_gesture)
                        print(f"MQTT Published: {current_gesture}", file=sys.stderr)
                        last_send_time[i] = current_time

                temp_data[i] = current_gesture
        
        # ... (?붾㈃??洹몃━???섎㉧吏 濡쒖쭅)
        cv2.imshow('Hand Tracking', image)
        if cv2.waitKey(1) == 27:
            break

    detector.close()
    cap.release()
    cv2.destroyAllWindows()
    mqtt_client.loop_stop() # ?ㅽ겕由쏀듃 醫낅즺 ??MQTT 猷⑦봽 ?뺤?

def main():
    # (湲곗〈 run_hands.py??main ?⑥닔? ?숈씪)
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--task', help='The hand tracking task to run.', required=False, choices=['gesture_recognizer', 'hand_landmarker'], default='gesture_recognizer')
    parser.add_argument('--model', help='Name of the model bundle.', required=False, default='gesture_recognizer.task')
    # ... (?ㅻⅨ argparse ?몄옄??
    parser.add_argument('--numHands', help='Max number of hands that can be detected.', required=False, default=2)
    parser.add_argument('--minHandDetectionConfidence', help='The minimum confidence score for hand detection.', required=False, default=0.5)
    parser.add_argument('--minHandPresenceConfidence', help='The minimum confidence score of hand presence.', required=False, default=0.5)
    parser.add_argument('--minTrackingConfidence', help='The minimum confidence score for hand tracking.', required=False, default=0.5)
    parser.add_argument('--cameraId', help='Id of camera.', required=False, default=0)
    parser.add_argument('--frameWidth', help='Width of frame to capture from camera.', required=False, default=640)
    parser.add_argument('--frameHeight', help='Height of frame to capture from camera.', required=False, default=480)
    args = parser.parse_args()

    run(args.model, int(args.numHands), float(args.minHandDetectionConfidence),
        float(args.minHandPresenceConfidence), float(args.minTrackingConfidence),
        int(args.cameraId), args.frameWidth, args.frameHeight, args.task)


if __name__ == '__main__':
    main()

