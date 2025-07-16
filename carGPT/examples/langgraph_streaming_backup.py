import asyncio

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph

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
app = workflow.compile()


async def generate(inputs, config):
    whole_msg = ""
    async for msg, metadata in app.astream(
        {"messages": inputs}, config, stream_mode="messages"
    ):
        if msg.content and not isinstance(msg, HumanMessage):
            whole_msg += msg.content
            yield whole_msg

async def main():
    inputs = [{"role": "user", "content": "what can you tell me about paris!"}]
    config = {"configurable": {"session_id": "123"}}
    async for msg in generate(inputs, config):
        print(msg, flush=True)
            

asyncio.run(main())