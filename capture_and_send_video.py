import cv2
import requests
import tempfile

url = "http://localhost:8000/api/verify/kyc"

# Change this if the default camera is not the one you want
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    raise SystemExit("Cannot open webcam")

frames = []
print("Recording 60 seconds of video (600 frames at 30 FPS)...")
print("Press 'q' to stop early...\n")

for i in range(600):
    ret, frame = cap.read()
    if not ret:
        break
    frames.append(frame)
    
    # Display frame so you can see yourself recording
    cv2.imshow("Recording... Press q to stop", frame)
    
    if (i + 1) % 100 == 0:
        print(f"  Captured {i + 1}/600 frames...")
    
    # Press 'q' to stop early
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("Stopped early")
        break

cap.release()
cv2.destroyAllWindows()

if not frames:
    raise SystemExit("No frames captured from webcam")

print(f"Total frames captured: {len(frames)}")

with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
    video_path = tmp.name

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
height, width = frames[0].shape[:2]
writer = cv2.VideoWriter(video_path, fourcc, 30.0, (width, height))
for frame in frames:
    writer.write(frame)
writer.release()

print("Sending video to server for face-based lookup...")

files = {
    "video_stream": open(video_path, "rb")
}
data = {
    "device_id": "webcam_device_01",
    "device_model": "webcam",
    "os": "windows"
}

response = requests.post(url, data=data, files=files)
print(response.status_code)
print(response.text)
