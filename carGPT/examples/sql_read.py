import os
os.environ["OPENAI_API_KEY"] = "..."

from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI


if __name__ == '__main__':
    db = SQLDatabase.from_uri("sqlite:///articles.db")
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True)
    res = agent_executor.invoke("list all toyota cars from the articles that are newer than 2020")