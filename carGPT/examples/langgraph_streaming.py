import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel


class ChatResponse(BaseModel):
    content: str

    def encode(self) -> str:
        return "data: " + self.model_dump_json() + "\n\n"


app = FastAPI()


model = ChatOpenAI(
    model="gpt-4o-mini",
    api_key="...",
)

    
chat_histories = {}


def get_chat_history(session_id: str) -> ChatMessageHistory:
    if session_id not in chat_histories:
        chat_histories[session_id] = ChatMessageHistory()
    return chat_histories[session_id]


async def call_model(state: MessagesState, config: RunnableConfig):
    if "configurable" not in config or "session_id" not in config["configurable"]:
        raise ValueError(
            "Make sure that the config includes the following information: {'configurable': {'session_id': 'some_value'}}"
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

    # Create a generator for streaming response
    async def event_generator():
        input_message = HumanMessage(content=user_message)
        async for event, _ in graph.astream(
            {"messages": [input_message]}, config, stream_mode="messages"
        ):
            yield ChatResponse(content=event.content).encode()

    return StreamingResponse(event_generator())
