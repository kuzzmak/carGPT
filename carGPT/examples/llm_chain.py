from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


if __name__ == "__main__":
    model = ChatOpenAI(model="gpt-3.5-turbo")
    messages = [
        SystemMessage(
            content="Translate the following from English into Italian"
        ),
        HumanMessage(content="hi!"),
    ]
    system_template = "Translate the following into {language}:"
    prompt_template = ChatPromptTemplate.from_messages(
        [("system", system_template), ("user", "{text}")]
    )
    result = prompt_template.invoke({"language": "italian", "text": "hi"})
    print(result)
    # parser = StrOutputParser()
    # chain = model | parser
    # res = chain.invoke(messages)
    # print(res)
