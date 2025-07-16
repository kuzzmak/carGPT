import os

os.environ["GOOGLE_CSE_ID"] = "..."
os.environ["GOOGLE_API_KEY"] = "..."

from langchain_community.utilities import GoogleSearchAPIWrapper
from langchain_core.tools import Tool

search = GoogleSearchAPIWrapper()

tool = Tool(
    name="google_search",
    description="Search Google for recent results.",
    func=search.run,
)

res = tool.run("python")
print(res)