from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_community.utilities import SQLDatabase
from typing_extensions import Annotated, TypedDict
import psycopg2
from langchain import hub


class QueryOutput(TypedDict):
    """Generated SQL query."""

    query: Annotated[str, ..., "Syntactically valid SQL query."]
    

username = "adsuser"
password = "pass"
host = "localhost"
port = "5432"
mydatabase = "ads_db"
pg_uri = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{mydatabase}"
# db = SQLDatabase.from_uri(pg_uri)
# print(db.table_info)

query_prompt_template = hub.pull("langchain-ai/sql-query-system-prompt")

query_prompt_template.messages[0].pretty_print()

# llm = ChatOpenAI(
#     model="gpt-4o-mini",
#     api_key="...",
# )

# sql_query_construction_llm = ChatOpenAI(
#     model="gpt-4o-mini",
#     api_key="...",
# )
# sql_query_construction_llm_prompt = """
# You are an expert in constructing SQL query from past messages.

# These messages are from assistant and user. Assistant is trying to 
# """

# # Define a new graph
# workflow = StateGraph(state_schema=MessagesState)


# # Define the function that calls the model
# def call_model(state: MessagesState):
#     system_prompt = (
#         "You are a expert in recommending which car(s) user should buy based on their preference. "
#         "User should give you info about his budget, does he want an automatic transmission or manual, what color and so on. "
#         "Fields for which you should ask for user input are listed bellow. "
#         "Also allow the user to not give all the information, maybe he is fine with either automatic and manual transmission or does not have color preference. "
#         "---"
#         "FIELDS: "
#         "\tprice, transmission, color, model year, make"
#     )
#     messages = [SystemMessage(content=system_prompt)] + state["messages"]
#     response = llm.invoke(messages)
#     return {"messages": response}


# # Define the (single) node in the graph
# workflow.add_edge(START, "model")
# workflow.add_node("model", call_model)

# # Add memory
# memory = MemorySaver()
# app = workflow.compile(checkpointer=memory)

# config = {"configurable": {"thread_id": "1"}}

# while True:
#     user_input = input("You: ")
#     if user_input.lower() in ["exit", "quit"]:
#         print("Chatbot: Goodbye!")
#         break
#     output = app.invoke(
#         {"messages": [HumanMessage(content=user_input)]},
#         config={"configurable": {"thread_id": "1"}},
#     )
#     output["messages"][-1].pretty_print()
