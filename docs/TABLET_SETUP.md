# Tablet setup

The tablet page is a browser-based camera and rover link. The laptop hosts the app and performs image analysis. The tablet is not an independent disease-analysis computer.

## A. Prepare the laptop

1. Start AgriSahayak on the laptop with `python server.py`.
2. For a tablet connected over a trusted private Wi-Fi network, set `HOST = "0.0.0.0"` in `config.py` before starting the server. This exposes the dashboard API on the laptop's local network. Do not port-forward it or use public/untrusted Wi-Fi: the prototype has no login system.
3. Find the laptop's local IP address with `ipconfig` and note its IPv4 address, for example `192.168.1.20`.
4. Allow Python through Windows Firewall only on the Private network if Windows asks.

For a laptop-only check, keep the safer default `HOST = "127.0.0.1"` and open `http://127.0.0.1:8000` on that laptop.

## B. Open the tablet camera page

1. Connect the tablet and laptop to the same trusted Wi-Fi network or private hotspot.
2. On the tablet, open Chrome and enter `http://<LAPTOP-IP>:8000/tablet.html`, replacing `<LAPTOP-IP>` with the laptop IPv4 address.
3. Allow camera access when Chrome prompts. Choose the rear camera in tablet settings if needed.
4. Tap **Start camera**. Tap **Full screen** to hide browser controls.
5. Tap the shutter for one image, or enable **Auto** and select a capture interval. Keep the page open while automatic capture is active.
6. The tablet keeps queued images locally while disconnected. When the laptop server becomes reachable again, queued captures can sync; the laptop then analyzes received images.

## C. Connect Arduino using USB OTG (optional)

1. Use a tablet/browser that supports Web Serial (typically Chrome on a supported Android device).
2. Connect the Arduino to the tablet through the correct USB OTG adapter and data cable.
3. In the tablet page, tap **Connect Arduino**, choose the serial device, and grant access.
4. Confirm the tablet status shows the serial link as connected and that readings arrive before sending motor commands.
5. Keep rover wheels lifted for the first command. Use short, low-speed movement and stop immediately if a motor runs the wrong way.

The tablet may need to reach the laptop server over Wi-Fi while it is connected to the Arduino over USB OTG. The USB serial link alone does not provide laptop model inference or dashboard access.

## Offline behavior

| Function | Offline from laptop? |
|---|---|
| Take/store a tablet photo locally | Yes, while the tablet page remains open and camera permission is granted |
| Run AgriSahayak leaf/produce models on the tablet | No; inference is on the laptop |
| Send new readings/photos to the laptop | No; they wait until the connection returns |
| Use the laptop's Ollama/Groq/xAI assistant | No; those services run or connect from the laptop |
| Control Arduino directly from tablet USB OTG | Possible if the board, browser and USB Serial permissions support it; it does not by itself activate laptop analysis |

The app is a demonstration prototype; verify browser, camera, network and serial behavior on the actual tablet before relying on it.

