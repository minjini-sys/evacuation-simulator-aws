import requests
import time

last_message = None

while True:
    response = requests.get('http://168.107.59.104:5000/get_chats')
    chats = response.json()
    
    if chats:
        latest = chats[-1]
        
        # 이전과 다를 때만 출력
        if latest != last_message:
            print(f"{latest['player']}: {latest['message']}")
            last_message = latest
    
    time.sleep(2)