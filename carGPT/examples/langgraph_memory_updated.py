import uuid

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import START, MessagesState, StateGraph

chats_by_session_id = {}


def get_chat_history(session_id: str) -> InMemoryChatMessageHistory:
    chat_history = chats_by_session_id.get(session_id)
    if chat_history is None:
        chat_history = InMemoryChatMessageHistory()
        chats_by_session_id[session_id] = chat_history
    return chat_history


llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key="...",
)

# Define a new graph
builder = StateGraph(state_schema=MessagesState)


# Define the function that calls the model
def call_model(
    state: MessagesState, config: RunnableConfig
) -> list[BaseMessage]:
    # Make sure that config is populated with the session id
    if (
        "configurable" not in config
        or "session_id" not in config["configurable"]
    ):
        raise ValueError(
            "Make sure that the config includes the following information: {'configurable': {'session_id': 'some_value'}}"
        )
    # Fetch the history of messages and append to it any new messages.
    chat_history = get_chat_history(config["configurable"]["session_id"])
    messages = list(chat_history.messages) + state["messages"]
    ai_message = llm.invoke(messages)
    # Finally, update the chat message history to include
    # the new input message from the user together with the
    # repsonse from the model.
    chat_history.add_messages(state["messages"] + [ai_message])
    return {"messages": ai_message}


# Define the (single) node in the graph
builder.add_edge(START, "model")
builder.add_node("model", call_model)

graph = builder.compile()

session_id = uuid.uuid4()
config = {"configurable": {"session_id": session_id}}

while True:
    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit"]:
        print("Chatbot: Goodbye!")
        break
    output = graph.invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
    )
    output["messages"][-1].pretty_print()
