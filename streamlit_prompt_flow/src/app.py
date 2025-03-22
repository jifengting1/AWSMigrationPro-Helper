import asyncio
import json
import boto3
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

FILE_ROOT = Path(__file__).parent

session = boto3.Session()

bedrock_agent_client = session.client(service_name='bedrock-agent-runtime')

# Define the flow identifier and alias identifier
flow_identifier = 'arn:aws:bedrock:us-east-1:150123420273:flow/DJVL78MHJZ'
alias_identifier = 'arn:aws:bedrock:us-east-1:150123420273:flow/DJVL78MHJZ/alias/80VZO4XGKU'

def render_messages(messages: list, assistant_avatar: str | None = None):
    for message in messages:
        match message["role"]:
            case "user":
                with st.chat_message("user"):
                    st.markdown(message["content"])
            case "assistant":
                if assistant_avatar is None:
                    with st.chat_message("assistant"):
                        st.markdown(message["content"])
                else:
                    with st.chat_message("assistant", avatar=assistant_avatar):
                        st.markdown(message["content"])

def query_bedrock_prompt_flow(messages_key: str):
    messages=st.session_state.messages[messages_key]
    #convert messages to a string
    messages_string = json.dumps(messages)
    
    # Define the input objects for the flow
    input_objects = [
        {
            "nodeName": "FlowInputNode",
            "nodeOutputName": "document",
            "content": {
                "document": messages_string
            }
        }
    ]

    try:
        # Invoke the flow
        response = bedrock_agent_client.invoke_flow(
            flowIdentifier=flow_identifier,
            flowAliasIdentifier=alias_identifier,
            inputs=input_objects
        )
        
        # Get the FlowResponseStream
        response_stream = response['responseStream']

        for event in response_stream:
            if 'flowOutputEvent' in event:
                yield event['flowOutputEvent']['content']['document']

    except Exception as e:
        st.error(e)
        print(e)
        # Remove the previous human prompt from chat history
        st.session_state.messages[messages_key].pop()
        st.stop()
    
async def get_reply(
    container: st.container,
    messages_key: str,
    prompt: str,
    loading_fp: Path = FILE_ROOT / "loading.gif",
):
    with container:
        # Render new human prompt
        with st.chat_message("user"):
            st.markdown(prompt)

        # Add prompt to chat history
        st.session_state.messages[messages_key].append({"role": "user", "content": prompt})

        # Render new response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            try:
                full_response = st.write_stream(query_bedrock_prompt_flow(messages_key))
            except Exception as e:
                message_placeholder.empty()
                st.error(e)
                print(e)
                # Remove the previous human prompt from chat history
                st.session_state.messages[messages_key].pop()
                st.stop()

        # Add response to chat history
        st.session_state.messages[messages_key].append({"role": "assistant", "content": full_response})

async def main():

    aws_account = session.client('sts').get_caller_identity().get('Account')  

    st.set_page_config(
        page_title=f'DemoAI - Account({aws_account})',
        page_icon="",
        layout="wide"
    )

    if "dummy_counter" not in st.session_state:
        st.session_state.dummy_counter = 0
    if "messages" not in st.session_state:
        st.session_state.messages = {}

    title = f'# Demo<i>AI</i> - Account({aws_account})'

    st.markdown(title, unsafe_allow_html=True)
    with st.container():
        # Render model columns
        columns = st.columns(1)
        messages_key = "prompt_flow"
        if messages_key not in st.session_state.messages:
            st.session_state.messages[messages_key] = []
        with columns[0]:
            render_messages(st.session_state.messages[messages_key], None)
        
    with st.container():
        placeholder_text = "Send a message to the model"
    
        with st.form("prompt_form", clear_on_submit=True):
            prompt = st.text_area(
                "Prompt",
                placeholder=placeholder_text, 
                label_visibility="collapsed",
                height=50,
            )
            prompt_submitted = st.form_submit_button("Send", type="primary")
        if st.button("Clear all message histories"):
            st.session_state.messages = {}
            st.rerun()
    
        if prompt_submitted:
            await asyncio.gather(get_reply(columns[0], messages_key, prompt))
            st.rerun()

if __name__ == "__main__":
    asyncio.run(main())