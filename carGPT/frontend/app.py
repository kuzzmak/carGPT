import json
import os
import uuid

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.title("Chatbot Application")

# Generate or retrieve session ID
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "How can I help you?"}
    ]

# Display chat messages from history
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])


# User input
if prompt := st.chat_input():
    # Update chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # API request to backend
    # url = "http://backend:8000/chat"
    url = f"{BACKEND_URL}/chat"
    headers = {"Content-Type": "application/json"}
    data = {"message": prompt, "session_id": st.session_state.session_id}

    # Stream the response
    response_text = ""

    with st.empty():
        response = requests.post(url, json=data, stream=True)
        if response.status_code == 200:
            for chunk in response.iter_lines():
                if chunk:
                    decoded_chunk = chunk.decode("utf-8")[6:]
                    json_obj = json.loads(decoded_chunk)
                    decoded_text = json_obj["content"]
                    response_text += decoded_text
                    st.chat_message("assistant").write(response_text)
        else:
            st.error(f"Error: {response.status_code}")

    # Update chat history with bot response
    st.session_state.messages.append({"role": "assistant", "content": response_text})
