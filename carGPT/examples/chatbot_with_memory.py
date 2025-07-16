from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

from dotenv import load_dotenv

EXAMPLES_DIR = Path(__file__).parent
load_dotenv(EXAMPLES_DIR / '.env')


# Set up the memory
memory = ConversationBufferMemory()

# Initialize the language model (replace 'your-openai-api-key' with your OpenAI key)
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.7,
    openai_api_key="...",
)

# Create a conversation chain with memory
conversation = ConversationChain(
    llm=llm,
    memory=memory,
    verbose=True,  # To see the debug outputs
)

# Interact with the chatbot
print("Chatbot: Hello! How can I assist you today?")
while True:
    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit"]:
        print("Chatbot: Goodbye!")
        break
    response = conversation.predict(input=user_input)
    print(f"Chatbot: {response}")
