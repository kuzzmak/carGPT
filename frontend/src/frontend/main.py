import datetime
import json
import os
import re
from uuid import uuid4

import requests
import streamlit as st
from htbuilder import div, styles
from htbuilder.units import rem

BACKEND_URL = os.environ["BACKEND_URL"]
CHAT_ENDPOINT = f"{BACKEND_URL}/chat"
USER_ID = os.environ["USER_ID"]


def render_ad_card(ad_data: dict):
    """Render a single ad card with images."""
    with st.container(border=True):
        # Title
        st.markdown(
            f"### {ad_data.get('make', '')} {ad_data.get('model', '')}"
        )

        # Display images in a carousel or gallery
        images = ad_data.get("images", [])
        if images:
            # Show up to 3 images in columns
            num_images = min(3, len(images))
            cols = st.columns(num_images)
            for idx, img_url in enumerate(images[:num_images]):
                with cols[idx]:
                    try:
                        st.image(img_url, use_container_width=True)
                    except Exception:
                        st.caption("⚠️ Image unavailable")

        # Display key metrics in columns
        col1, col2, col3 = st.columns(3)
        with col1:
            if ad_data.get("price"):
                st.metric("Price", f"€{ad_data['price']:,.0f}")
        with col2:
            if ad_data.get("manufacture_year"):
                st.metric("Year", ad_data["manufacture_year"])
        with col3:
            if ad_data.get("mileage"):
                st.metric("Mileage", f"{ad_data['mileage']:,} km")

        # Additional details in two columns
        col_a, col_b = st.columns(2)
        with col_a:
            if ad_data.get("location"):
                st.text(f"📍 {ad_data['location']}")
            if ad_data.get("engine"):
                st.text(f"⚙️ {ad_data['engine']}")
        with col_b:
            if ad_data.get("transmission"):
                st.text(f"🔧 {ad_data['transmission']}")
            if ad_data.get("power"):
                st.text(f"🏎️ {ad_data['power']} kW")

        # Link to full ad
        if ad_data.get("url"):
            st.link_button(
                "🔗 View Full Ad", ad_data["url"], use_container_width=True
            )


def parse_response_for_ads(response_text: str) -> list[dict]:
    """
    Parse the assistant's response to extract ad data from JSON code blocks.
    This extracts structured ad data that the LLM formats in ```json blocks.
    """
    ads = []
    # Look for JSON blocks in the response (both single-line and multi-line)
    json_pattern = r"```json\s*(\{.*?\})\s*```"
    matches = re.finditer(json_pattern, response_text, re.DOTALL)

    for match in matches:
        try:
            ad_data = json.loads(match.group(1))
            # Verify it's ad data by checking for required fields
            if "id" in ad_data and "make" in ad_data:
                ads.append(ad_data)
        except json.JSONDecodeError:
            continue

    return ads


def fetch_conversations():
    """Fetch user conversations from the backend API."""
    try:
        conversations_endpoint = f"{BACKEND_URL}/conversations/{USER_ID}"
        response = requests.get(conversations_endpoint)

        if response.status_code == 200:
            conversations_data = response.json()

            # Convert backend response to frontend format
            conversations = []
            for conv in conversations_data:
                # Extract conversation data based on your backend's Conversation model
                session_id = conv.get("conversation_id", "")
                messages = conv.get("messages", [])

                # Create a title from the first user message or use session_id
                title = f"Chat {session_id[:8]}..."
                if messages:
                    # Try to get the first user message for the title
                    first_user_msg = next(
                        (msg for msg in messages if msg.get("role") == "user"),
                        None,
                    )
                    if first_user_msg:
                        content = first_user_msg.get("content", "")
                        title = (
                            content[:30] + "..."
                            if len(content) > 30
                            else content
                        )

                # Convert message format if needed
                formatted_messages = []
                for msg in messages:
                    formatted_messages.append(
                        {
                            "role": msg.get("role", ""),
                            "content": msg.get("content", ""),
                        }
                    )

                conversations.append(
                    {
                        "session_id": session_id,
                        "title": title,
                        "messages": formatted_messages,
                        "message_count": len(formatted_messages),
                    }
                )

            return conversations

        st.error(f"Failed to fetch conversations: {response.status_code}")
        return []

    except requests.exceptions.RequestException as e:
        st.error(f"Connection error while fetching conversations: {e}")
        return []
    except Exception as e:
        st.error(f"Unexpected error while fetching conversations: {e}")
        return []


st.set_page_config(page_title="carGPT", page_icon="🚗")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize conversations once per session (reloaded on full page refresh)
if "conversations" not in st.session_state:
    st.session_state.conversations = fetch_conversations()
    st.session_state.conversations_by_id = {
        c["session_id"]: c for c in st.session_state.conversations
    }

# Sidebar: past conversations and new chat action
conversations = st.session_state.conversations
conversations_by_id = st.session_state.conversations_by_id

with st.sidebar:
    st.subheader("Past conversations")
    if st.button("New chat", use_container_width=True):
        st.session_state.session_id = str(uuid4())
        st.session_state.messages = []
        st.session_state.pop("initial_question", None)
        st.session_state.pop("selected_suggestion", None)
        st.rerun()

    for conv in conversations:
        label = conv.get("title") or conv["session_id"]
        if st.button(
            label,
            key=f"conv_btn_{conv['session_id']}",
            use_container_width=True,
        ):
            # Load selected conversation without re-fetching the list
            selected_id = conv["session_id"]
            conv_map = st.session_state.conversations_by_id
            if selected_id in conv_map:
                st.session_state.session_id = selected_id
                st.session_state.messages = conv_map[selected_id][
                    "messages"
                ].copy()
                st.session_state.pop("initial_question", None)
                st.session_state.pop("selected_suggestion", None)
            st.rerun()


SUGGESTIONS = {
    ":blue[:material/directions_car:] Compare two cars": (
        "Compare Tesla Model 3 vs BMW i4. Focus on range, performance, charging, tech, and price."
    ),
    ":green[:material/build_circle:] Maintenance schedule advice": (
        "What's the maintenance schedule for a 2018 Toyota Corolla? Include intervals and estimated costs."
    ),
    ":orange[:material/price_change:] Financing and total cost": (
        "Estimate total cost of ownership for a 2020 Honda Civic over 5 years, including insurance, maintenance, fuel, and depreciation."
    ),
    ":violet[:material/electric_bolt:] EV charging and range": (
        "How do I plan long road trips with an EV? Tips for charging networks, planning stops, and range management."
    ),
    ":red[:material/shopping_cart:] Buying a used car checklist": (
        "Give me a checklist for inspecting a used car before buying and common red flags to avoid."
    ),
}


def get_response(prompt):
    """Stream response from backend chat endpoint."""
    try:
        # Prepare the chat request
        chat_request = {
            "user_id": USER_ID,
            "session_id": st.session_state.session_id,
            "message": prompt,
        }

        # Make streaming request to backend
        response = requests.post(
            CHAT_ENDPOINT,
            json=chat_request,
            stream=True,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            st.error(f"Backend error: {response.status_code}")
            return

        # Stream the response chunk by chunk
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode("utf-8")
                if decoded_line.startswith("data: "):
                    chunk = decoded_line[6:]  # Remove 'data: ' prefix
                    if chunk:
                        # Unescape newlines that were escaped for SSE format
                        unescaped_chunk = chunk.replace("\\n", "\n").replace(
                            "\\r", "\r"
                        )
                        yield unescaped_chunk

    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {e}")
        yield "Sorry, I'm having trouble connecting to the backend service."
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        yield "Sorry, something went wrong while processing your request."


# -----------------------------------------------------------------------------
# Draw the UI.


st.html(div(style=styles(font_size=rem(5), line_height=1))["❉"])

title_row = st.container(
    horizontal=True,
    vertical_alignment="bottom",
)

with title_row:
    st.title(
        # ":material/cognition_2: Streamlit AI assistant", anchor=False, width="stretch"
        "carGPT assistant",
        anchor=False,
        width="stretch",
    )

user_just_asked_initial_question = (
    "initial_question" in st.session_state
    and st.session_state.initial_question
)

user_just_clicked_suggestion = (
    "selected_suggestion" in st.session_state
    and st.session_state.selected_suggestion
)

user_first_interaction = (
    user_just_asked_initial_question or user_just_clicked_suggestion
)

has_message_history = (
    "messages" in st.session_state and len(st.session_state.messages) > 0
)

# Show a different UI when the user hasn't asked a question yet.
if not user_first_interaction and not has_message_history:
    st.session_state.messages = []

    with st.container():
        st.chat_input("Ask a question...", key="initial_question")

        selected_suggestion = st.pills(
            label="Examples",
            label_visibility="collapsed",
            options=SUGGESTIONS.keys(),
            key="selected_suggestion",
        )

    st.stop()

# Show chat input at the bottom when a question has been asked.
user_message = st.chat_input("Ask a follow-up...")

if not user_message:
    if user_just_asked_initial_question:
        user_message = st.session_state.initial_question
    if user_just_clicked_suggestion:
        user_message = SUGGESTIONS[st.session_state.selected_suggestion]

if "prev_question_timestamp" not in st.session_state:
    st.session_state.prev_question_timestamp = datetime.datetime.fromtimestamp(
        0
    )

# Display chat messages from history as speech bubbles.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.container()  # Fix ghost message bug.

        st.markdown(message["content"])

if user_message:
    # Streamlit's Markdown engine interprets "$" as LaTeX code (used to
    # display math). The line below fixes it.
    user_message = user_message.replace("$", r"\$")

    # Display message as a speech bubble.
    with st.chat_message("user"):
        st.markdown(user_message)

    # Display assistant response as a speech bubble.
    with st.chat_message("assistant"):
        response_gen = get_response(user_message)

        accumulated_response = ""
        # Render spinner above the streamed content so it doesn't move down
        with st.spinner("Thinking..."):
            # Create the placeholder after the spinner so content appears below it
            response_placeholder = st.empty()
            json_start = False
            raw_response = ""
            for chunk in response_gen:
                raw_response += chunk.strip()
                if not json_start:
                    if chunk == "```":
                        json_start = True
                        continue

                    accumulated_response += chunk
                    response_placeholder.markdown(accumulated_response)

                if raw_response.endswith("```"):
                    json_start = False
                
        # Store the final response
        response = accumulated_response

    # Parse and display ad cards if any were found in the response
    ads = parse_response_for_ads(response)
    if ads:
        st.markdown("---")
        st.markdown("### 🚗 Suggested Vehicles")
        for ad in ads:
            render_ad_card(ad)

    # Add messages to chat history.
    st.session_state.messages.append({"role": "user", "content": user_message})
    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )


# ff.close()