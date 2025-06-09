import asyncio
import os
import streamlit as st
from textwrap import dedent

# Import after streamlit to avoid event loop conflicts
from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

st.set_page_config(page_title="Browser MCP Agent", layout="wide")

st.markdown("<h1 style='text-align: center;'>Browser MCP Agent</h1>", unsafe_allow_html=True)
st.markdown("Interact with a powerful web browsing agent that can navigate and interact with websites")

with st.sidebar:
    st.markdown("### Configuration")
    # Add API key input
    api_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    
    st.markdown("### Example commands")
    st.markdown("**Navigation**")
    st.markdown("- Go to wikipedia.org/wiki/computer_vision")
    
    st.markdown("**Interaction**")
    st.markdown("- Click on the link to object detection and take a screenshot")
    st.markdown("- Scroll down and summarize the page")
    
    st.markdown("**Multi-step Tasks**")
    st.markdown("- Navigate to wikipedia.org/wiki/computer_vision, scroll down and report details")
    st.markdown("- Scroll down and summarize the wikipedia page")
    
    st.caption("The agent uses puppeteer to control the browser")

query = st.text_area("Your command", 
                    placeholder="Ask the agent to navigate to websites and interact with them",
                    height=100)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.mcp_app = MCPApp(name="streamlit_mcp_agent")
    st.session_state.mcp_context = None
    st.session_state.mcp_agent_app = None
    st.session_state.browser_agent = None
    st.session_state.llm = None
    st.session_state.loop = None  # Will initialize later when needed

async def setup_agent():
    if not st.session_state.initialized:
        try:
            # Initialize event loop if not exists
            if st.session_state.loop is None:
                st.session_state.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(st.session_state.loop)
            
            st.session_state.mcp_context = st.session_state.mcp_app.run()
            st.session_state.mcp_agent_app = await st.session_state.mcp_context.__aenter__()

            st.session_state.browser_agent = Agent(
                name="browser",
                instruction=dedent("""\
                You are a helpful web browsing assistant that can interact with websites using puppeteer.
                - Navigate to websites and perform browser actions (click, scroll, type)
                - Extract information from web pages
                - Take screenshots of page elements when useful
                - Provide concise summaries of web content using markdown
                - Follow multi-step browsing sequences to complete tasks
                """),
                server_names=["puppeteer"]
            )

            await st.session_state.browser_agent.initialize()
            st.session_state.llm = await st.session_state.browser_agent.attach_llm(OpenAIAugmentedLLM)

            logger = st.session_state.mcp_agent_app.logger
            tools = await st.session_state.browser_agent.list_tools()
            logger.info(f"Tools available: {tools}")

            st.session_state.initialized = True
            return None
        except Exception as e:
            return f"Error during initialization: {str(e)}"
    return None

async def run_mcp_agent(message):
    # Check API key first
    if not os.getenv("OPENAI_API_KEY"):
        return "Error: No OpenAI API key provided. Please add your key in the sidebar."
    
    try:
        error = await setup_agent()
        if error:
            return error
        
        result = await st.session_state.llm.generate_str(
            message=message,
            request_params=RequestParams(use_history=True)
        )

        return result
    except Exception as e:
        return f"Agent execution error: {str(e)}"
    
if st.button("Run command", type="primary", use_container_width=True):
    if not query.strip():
        st.warning("Please enter a command")
        st.stop()
        
    with st.spinner("Processing your request..."):
        try:
            # Create event loop if not exists
            if st.session_state.loop is None:
                st.session_state.loop = asyncio.new_event_loop()
            
            result = st.session_state.loop.run_until_complete(run_mcp_agent(query))
        except Exception as e:
            result = f"Runtime error: {str(e)}"
        finally:
            # Reset event loop after execution
            if st.session_state.loop:
                st.session_state.loop.close()
                st.session_state.loop = None

    st.markdown("### Response")
    st.markdown(result)
    
    # Add debug info
    with st.expander("Session State Info"):
        st.json({
            "initialized": st.session_state.initialized,
            "openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
            "agent_status": "Ready" if st.session_state.initialized else "Not initialized"
        })