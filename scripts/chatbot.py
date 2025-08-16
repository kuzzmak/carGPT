from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel

load_dotenv()


class ChatResponse(BaseModel):
    content: str

    def encode(self) -> str:
        return "data: " + self.model_dump_json() + "\n\n"


app = FastAPI()


model = ChatOpenAI(model="gpt-4o-mini")


chat_histories = {}


def get_chat_history(session_id: str) -> ChatMessageHistory:
    if session_id not in chat_histories:
        chat_histories[session_id] = ChatMessageHistory()
    return chat_histories[session_id]


async def call_model(state: MessagesState, config: RunnableConfig):
    if (
        "configurable" not in config
        or "session_id" not in config["configurable"]
    ):
        raise ValueError(
            "Make sure that the config includes the following "
            "information: {'configurable': {'session_id': 'some_value'}}"
        )
    chat_history = get_chat_history(config["configurable"]["session_id"])
    messages = list(chat_history.messages) + state["messages"]
    response = await model.ainvoke(messages, config)
    return {"messages": response}


workflow = StateGraph(MessagesState)
workflow.add_node(call_model)
workflow.add_edge(START, "call_model")
workflow.add_edge("call_model", END)
graph = workflow.compile()


@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("message")
    session_id = data.get("session_id")
    if not user_message or not session_id:
        raise ValueError("Invalid request")

    config = {"configurable": {"session_id": session_id}}
    chat_history = get_chat_history(session_id)

    # Add the user's message to the chat history
    input_message = HumanMessage(content=user_message)
    chat_history.add_user_message(user_message)

    # Create a generator for streaming response
    async def event_generator():
        assistant_message_buffer = []  # To handle response in chunks
        async for event, _ in graph.astream(
            {"messages": [input_message]}, config, stream_mode="messages"
        ):
            assistant_message_buffer.append(event.content)
            yield ChatResponse(content=event.content).encode()

        # Append the full assistant message to the chat history after
        # the response is complete
        if assistant_message_buffer:
            full_assistant_message = "".join(assistant_message_buffer)
            chat_history.add_ai_message(full_assistant_message)

    return StreamingResponse(event_generator())
