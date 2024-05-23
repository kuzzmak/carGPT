from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


if __name__ == "__main__":
    model = ChatOpenAI(model="gpt-3.5-turbo")
    messages = [
        SystemMessage(
            content="Translate the following from English into Italian"
        ),
        HumanMessage(content="hi!"),
    ]
    res = model.invoke(messages)

    print(res)
