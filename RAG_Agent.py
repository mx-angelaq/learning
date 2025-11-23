from dotenv import load_dotenv
import os
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage
from operator import add as add_messages
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.tools import tool
# Load environment variables from .env file

load_dotenv()

llm = ChatOpenAI(
    model = "gpt-4o", temperature=0) # i want to minimize hallucinations 


# Our embedding model - has to be compatible with the LLM we use
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
)

pdf_path = r"C:\Users\Angela\Downloads\Stock_Market_Performance_2024.pdf"

# Safety measure for debugging purposes
if not os.path.exists(pdf_path):
    raise FileNotFoundError(f"PDF file not found at path: {pdf_path}")

pdf_loader = PyPDFLoader(pdf_path) # Load the PDF file

# Checks if the PDF was loaded correctly
try:
    pages = pdf_loader.load()
    print(f"Loaded {len(pages)} pages from the PDF.")
except Exception as e:
    print(f"Error loading PDF: {e}")
    raise

# Split the text into manageable chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)


pages_split = text_splitter.split_documents(pages) # Apply this to  pages (split into chunks)

persist_directory = r"C:\Users\Angela\OneDrive - Aqore\Desktop\LearningLangGraph"
collection_name = "stock_market"

# If our collection does not exist in the directory, we create using the os command
if not os.path.exists(persist_directory):
    os.makedirs(persist_directory)

try:
    # create the chroma database using our embeddings model
    vectorstore = Chroma.from_documents(
        documents=pages_split,
        embedding=embeddings,
        persist_directory=persist_directory,
        collection_name=collection_name,
    )
    print(f"Created ChromaDB vector store!")

except Exception as e:
    print(f"Error creating ChromaDB vector store: {e}")
    raise

# now we create our retriever
retriever = vectorstore.as_retriever(
    search_type="similarity", 
    search_kwargs={"k": 3}) # K is the amount of chucks to return

@tool 
def retriever_tool(query: str) -> str:
    """
    This tool searches and returns the information from the stock market performance 2024 document.
    """

    docs = retriever.invoke(query)

    if not docs: 
        return "No relevant information found in the document."
    
    results = []
    for i, doc in enumerate(docs):
        results.append(f"Source {i+1}:\n{doc.page_content}\n")

    return "\n\n".join(results)

tools = [retriever_tool]

llm = llm.bind_tools(tools)

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

def should_continue(state: AgentState):
    """ Check if the last message contains tool calls"""
    result = state["messages"][-1]
    return hasattr(result, "tool_calls") and len(result.tool_calls) > 0

system_prompt = """
You are an intelligent AI assistant who answers questions about Stock Market Performance in 2024 based on the document loaded into your knowledgebase. 
Use the retriever tool available to answer questions about stock market performance data.
You can make multiple calls if needed. If you need to look up some information before
asking a follow up questione, you are allowed to do that. Please always cite the specific
parts of the documents you use in your answers. 
  """
tools_dict = {our_tool.name: our_tool for our_tool in tools} # create a dictionary of tools

#llm agent
def call_llm(state: AgentState) -> AgentState:
    """Function to call the LLM with the current state messages. """
    messages = list(state["messages"])
    messages = [SystemMessage(content=system_prompt)] + messages
    message = llm.invoke(messages)
    return {'messages': [message]}
 
#retriever agent
def take_action(state: AgentState) -> AgentState:
    """ Execute tool calls from the LLM's response. """
    tool_calls = state["messages"][-1].tool_calls
    results = []
    for t in tool_calls:
        print(f"Callng tool: {t['name']} with query:{t['args'].get('query', 'no query provided')}")
        if not t['name'] in tools_dict: # checks if a valid tool is present
            print(f"\Tool: {t['name']} not found!")
            result = "Incorrect tool name, please retry and select tool from list of available tools."

        else:
            result = tools_dict[t['name']].invoke(t['args'].get('query', ''))
            print(f" result length: {len(str(result))}")

    #appends the tool message
    results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))
    return {'messages': results}

graph = StateGraph(AgentState)
graph.add_node("llm", call_llm)
graph.add_node("retriever_agent", take_action)

graph.add_conditional_edges(
    "llm",
    should_continue,
    {True: "retriever_agent", False: END},
)
graph.add_edge("retriever_agent", "llm")
graph.set_entry_point("llm")

rag_agent = graph.compile()

def running_agent():
    print("\n\n=== RAG AGENT INITIALIZED ===\n")

    while True:
        user_input = input("\n What is your question:")
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting the RAG agent. Goodbye!")
            break
        messages = [HumanMessage(content=user_input)] # converts back to human message type
        result = rag_agent.invoke({'messages': messages})
        print(f"\n\n=== AGENT RESPONSE ===\n{result['messages'][-1].content}\n")
