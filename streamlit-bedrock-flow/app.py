import streamlit as st
import json
import pandas as pd
import boto3
from PIL import Image, ImageOps, ImageDraw
import os

# Streamlit page configuration
st.set_page_config(page_title="AWS MigrationPro", page_icon=":robot_face:", layout="wide")

# Function to crop image into a circle
def crop_to_circle(image):
    mask = Image.new('L', image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0) + image.size, fill=255)
    result = ImageOps.fit(image, mask.size, centering=(0.5, 0.5))
    result.putalpha(mask)
    return result

# Title
st.title("AWS MigrationPro")

# Display a text box for input
prompt = st.text_input("Please enter your question about migration?", max_chars=2000)
prompt = prompt.strip()

session = boto3.Session()
bedrock_agent_client = session.client(service_name='bedrock-agent-runtime')

# Define the flow identifier and alias identifier
flow_identifier = 'arn:aws:bedrock:us-east-1:150123420273:flow/DJVL78MHJZ'
alias_identifier = 'arn:aws:bedrock:us-east-1:150123420273:flow/DJVL78MHJZ/alias/80VZO4XGKU'


# Display a primary button for submission
submit_button = st.button("Submit", type="primary")

# Display a button to end the session
end_session_button = st.button("End Session")

# Session State Management
if 'history' not in st.session_state:
    st.session_state['history'] = []

# Function to parse and format response
def format_response(response_body):
    try:
        # Try to load the response as JSON
        data = json.loads(response_body)
        # If it's a list, convert it to a DataFrame for better visualization
        if isinstance(data, list):
            return pd.DataFrame(data)
        else:
            return response_body
    except json.JSONDecodeError:
        # If response is not JSON, return as is
        return response_body

# Handling user input and responses
if submit_button and prompt:
# Define the input objects for the flow
    input_objects = [
        {
            "nodeName": "FlowInputNode",
            "nodeOutputName": "document",
            "content": {
                "document": prompt
            }
        }
    ]
    response = bedrock_agent_client.invoke_flow(
                flowIdentifier=flow_identifier,
                flowAliasIdentifier=alias_identifier,
                inputs=input_objects
            )
    # Get the FlowResponseStream
    response_stream = response['responseStream']

    for event in response_stream:
        if 'flowOutputEvent' in event:
    
            try:
                # Parse the JSON string
                response_data= event['flowOutputEvent']['content']['document']
                print("TRACE & RESPONSE DATA ->  ", response_data)

            except json.JSONDecodeError as e:
                print("JSON decoding error:", e)
                response_data = None 
    

    # Use trace_data and formatted_response as needed
    # st.sidebar.text_area("", value=all_data, height=300)
    st.session_state['history'].append({"question": prompt, "answer": response_data})
    # st.session_state['trace_data'] = the_response
    st.session_state['prompt'] = "" # clear out input box
  

if end_session_button:
    st.session_state['history'].append({"question": "Session Ended", "answer": "Thank you for using AnyCompany Support Agent!", "agent": selected_agent})
    event = {
        "sessionId": "MYSESSION",
        "question": "placeholder to end session",
        "endSession": True
    }
    agenthelper.lambda_handler(event, None)
    st.session_state['history'].clear()

MAX_HISTORY_WINDOW = 6

# Display recent messages in a structured layout
displayed_history = st.session_state['history'][-MAX_HISTORY_WINDOW:]

# Create a scrollable text area with the entire chat history
full_history_text = "<br><br>".join(
    [
        f"<b>You:</b>&nbsp;{chat['question'].strip()}<br><b>{chat['agent'].strip()}:</b>&nbsp;{chat['answer'].strip()}"
        for chat in st.session_state['history']
    ]
)

st.markdown(
    f"""
    <div style='
        background-color: #f8f9fa; 
        padding: 10px; 
        border-radius: 10px; 
        height: 300px; 
        overflow-y: auto; 
        border: 1px solid #ccc;
        color: black;
        font-family: Arial, sans-serif;
    '>
        {full_history_text}
    </div>
    """,
    unsafe_allow_html=True
)
