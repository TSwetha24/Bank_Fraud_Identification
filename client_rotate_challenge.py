"""Simple webcam client to perform a rotate challenge and POST frames to the API.

Usage:
  1. Start the API server: `uvicorn src.main:app --host 0.0.0.0 --port 8000`
  2. Run this script: `python client_rotate_challenge.py --user demo_user_001`

The script captures a short sequence of frames while prompting the user to rotate
the laptop/device, and sends each frame to `/api/verify/liveness` so the server's
motion and rPPG verifiers can accumulate state.
"""

import cv2
import argparse
import requests
import time
import sys


def post_frame(url, user_id, frame):
    _, img_encoded = cv2.imencode('.jpg', frame)
    files = {'face_image': ('frame.jpg', img_encoded.tobytes(), 'image/jpeg')}
    data = {'user_id': user_id}
    try:
        resp = requests.post(url, files=files, data=data, timeout=5)
        return resp
    except Exception as e:
        print(f"Request error: {e}")
        return None


def run_challenge(server_url, user_id, capture_index=0, frames=30, delay=0.1):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print('Cannot open webcam')
        return

    print('Press SPACE to start the rotate challenge. Press ESC to quit.')

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.putText(frame, 'Press SPACE to start challenge', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        cv2.imshow('Rotate Challenge', frame)
        k = cv2.waitKey(1) & 0xFF
        if k == 27:  # ESC
            cap.release()
            cv2.destroyAllWindows()
            return
        if k == 32:  # SPACE
            break

    print('Starting challenge: rotate device slowly left then right while camera captures frames...')
    time.sleep(0.5)

    last_resp = None
    for i in range(frames):
        ret, frame = cap.read()
        if not ret:
            break
        # Overlay guidance
        cv2.putText(frame, f'Frame {i+1}/{frames}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)
        cv2.imshow('Rotate Challenge', frame)

        resp = post_frame(f"{server_url}/api/verify/liveness", user_id, frame)
        if resp is not None:
            try:
                print(f'[{i+1}] Server response: {resp.status_code} {resp.json()}')
                last_resp = resp.json()
            except Exception:
                print(f'[{i+1}] Server returned status {resp.status_code}')

        if cv2.waitKey(1) & 0xFF == 27:
            break

        time.sleep(delay)

    cap.release()
    cv2.destroyAllWindows()

    print('\nChallenge complete.')
    if last_resp:
        print('Final liveness response:', last_resp)
    else:
        print('No response from server. Ensure API is running at provided URL.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default='http://localhost:8000', help='Server base URL')
    parser.add_argument('--user', default='demo_user_001', help='User ID')
    parser.add_argument('--frames', type=int, default=30, help='Number of frames to capture')
    parser.add_argument('--delay', type=float, default=0.1, help='Delay between frames (s)')
    args = parser.parse_args()

    run_challenge(args.server, args.user, frames=args.frames, delay=args.delay)


if __name__ == '__main__':
    main()
