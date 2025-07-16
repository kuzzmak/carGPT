import os
os.environ["OPENAI_API_KEY"] = "..."

from langchain.chains import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI


if __name__ == '__main__':
    connection_string = (
        "postgresql+psycopg2://adsuser:pass@localhost:5432/ads_db"
    )
    db = SQLDatabase.from_uri(connection_string)
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    chain = create_sql_query_chain(llm, db)
    # res = agent_executor.invoke("list all toyota cars from the articles that are newer than 2020")
    response = chain.invoke(
        {
            "question": "list all toyota cars from the articles that are newer than 2020"
        }
    )
    print(response)