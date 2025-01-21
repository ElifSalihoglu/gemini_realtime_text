from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from google import genai
import uvicorn
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL = "gemini-2.0-flash-exp"

client = genai.Client(
    http_options={
        'api_version': 'v1alpha',
    }
)

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chatbot</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f9;
            color: #333;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }

        .chat-container {
            width: 100%;
            max-width: 600px;
            background: #fff;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .chat-header {
            background: #6200ea;
            color: white;
            padding: 16px;
            text-align: center;
            font-size: 1.5rem;
        }

        .chat-messages {
            flex: 1;
            padding: 16px;
            overflow-y: auto;
            background: #f9f9f9;
        }

        .chat-messages ul {
            list-style: none;
            padding: 0;
        }

        .chat-messages li {
            margin-bottom: 12px;
            padding: 10px;
            border-radius: 6px;
            max-width: 80%;
        }

        .chat-messages .user {
            background: #6200ea;
            color: white;
            align-self: flex-end;
        }

        .chat-messages .bot {
            background: #e0e0e0;
            color: #333;
            align-self: flex-start;
        }

        .chat-input {
            display: flex;
            border-top: 1px solid #ddd;
        }

        .chat-input textarea {
            flex: 1;
            border: none;
            padding: 16px;
            font-size: 1rem;
            resize: none;
            outline: none;
        }

        .chat-input button {
            background: #6200ea;
            color: white;
            border: none;
            padding: 16px;
            font-size: 1rem;
            cursor: pointer;
            transition: background 0.3s;
        }

        .chat-input button:hover {
            background: #3700b3;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">Chatbot</div>
        <div class="chat-messages">
            <ul id="messages"></ul>
        </div>
        <div class="chat-input">
            <textarea id="messageInput" placeholder="Type your message here..."></textarea>
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>

    <script>
        let socket;

        function connectWebSocket() {
            socket = new WebSocket("ws://localhost:8000/ws");

            socket.onmessage = function(event) {
                const messages = document.getElementById('messages');
                const message = document.createElement('li');
                const data = JSON.parse(event.data);

                message.textContent = data.text || data.error || "Unknown response";
                message.className = data.error ? 'bot error' : 'bot';
                messages.appendChild(message);

                messages.scrollTop = messages.scrollHeight; // Scroll to bottom
            };
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const messages = document.getElementById('messages');

            if (socket && input.value.trim()) {
                const userMessage = document.createElement('li');
                userMessage.textContent = input.value.trim();
                userMessage.className = 'user';
                messages.appendChild(userMessage);

                socket.send(JSON.stringify({ text: input.value.trim() }));
                input.value = '';

                messages.scrollTop = messages.scrollHeight; // Scroll to bottom
            }
        }

        window.onload = connectWebSocket;
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        print("Connected to Gemini API")

        async def send_to_gemini():
            """Sends messages from the client websocket to the Gemini API."""
            try:
                async for message in websocket.iter_text():
                    try:
                        data = json.loads(message)
                        if "text" in data:
                            response = await client.aio.models.generate_content(
                                model=MODEL,
                                contents=[data["text"]]
                            )
                            # Debugging the raw response
                            print(f"Raw response: {response}")
                            response_text = "No response"

                            # Extract the plain text content from the response
                            if response.candidates:
                                first_candidate = response.candidates[0]
                                if hasattr(first_candidate, 'content') and hasattr(first_candidate.content, 'parts'):
                                    parts = first_candidate.content.parts
                                    response_text = "\n".join(part.text for part in parts if hasattr(part, 'text'))

                            await websocket.send_text(json.dumps({"text": response_text}))
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        await websocket.send_text(json.dumps({"error": str(e)}))
            except WebSocketDisconnect:
                print("WebSocket disconnected (send loop)")

        await send_to_gemini()

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"Error in WebSocket session: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
