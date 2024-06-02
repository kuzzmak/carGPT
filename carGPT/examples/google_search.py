import os

os.environ["GOOGLE_CSE_ID"] = "97d4ae88232bf4d29"
os.environ["GOOGLE_API_KEY"] = "AIzaSyAMCXHsKejCx81xJvtvN6Zojj_BBJKHchI"

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