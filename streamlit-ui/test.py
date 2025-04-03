import streamlit as st
import json
import pandas as pd


# Streamlit page configuration
st.set_page_config(page_title="AWS MigrationPro", page_icon=":rocket:", layout="wide")

import boto3
import uuid
from botocore.exceptions import NoCredentialsError
from graph import get_excel_data, create_radar_chart
from invoke_agent import BedrockAgentClient



# Initialize S3 client
s3 = boto3.client('s3', region_name="us-east-1")


# Agent IDs

DISCOVERY_AGENT_ID = "3SZXST6KPE"
DISCOVERY_AGENT_ALIAS_ID = "WGFQSGAZLG"
INFO_VALIDATION_AGENT_ID = "ATTGGAKZKM"
INFO_VALIDATION_AGENT_ALIAS = "LLHGNO10AV"
ANALYSIS_AGENT_ID = "LHSGIRXMNB"
ANALYSIS_AGENT_ALIAS = "JLQHOLUDY5"

def format_response(response_body):
    try:
        data = json.loads(response_body)
        if isinstance(data, list):
            return pd.DataFrame(data)
        else:
            return response_body
    except json.JSONDecodeError:
        return response_body

def display_graph(file):
    df = get_excel_data(file)
    if df is not None:
        st.write("Data from Excel:")
        st.write(df)
        
        fig = create_radar_chart(df)
        st.plotly_chart(fig)
    else:
        st.warning("Could not read data from the Excel file.")

def upload_to_s3(file, bucket_name, object_name):
    try:
        s3.upload_fileobj(file, bucket_name, object_name)
        return True
    except NoCredentialsError:
        st.error("Credentials not available")
        return False
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return False

def is_file_upload_complete(content: str) -> str:
    bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")

    system = [{
        "text": "You are a classifier that determines whether a message confirms that file upload is complete. Respond only with 'Yes' or 'No'. Do not explain."
    }]

    messages = [{
        "role": "user",
        "content": [{
            "text": f'Does this message mean the files were uploaded?\n\n""" {content} """'
        }]
    }]

    inf_params = {
        "maxTokens": 10,
        "temperature": 0.0,
        "topP": 0.1
    }

    response = bedrock_runtime.converse(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        messages=messages,
        system=system,
        inferenceConfig=inf_params
    )

    reply = response["output"]["message"]["content"][0]["text"].strip().lower()
    return "Yes" if reply.startswith("yes") else "No"

def is_config_complete(content: str) -> str:
    bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")

    system = [{
        "text": (
            "You are a classifier that determines whether a message confirms that the config file review is complete. "
            "Reply ONLY with 'Yes' or 'No'. Do not explain."
        )
    }]

    messages = [{
        "role": "user",
        "content": [{
            "text": f'Does this message confirm the config file is complete?\n\n""" {content} """'
        }]
    }]

    inf_params = {
        "maxTokens": 10,
        "temperature": 0.0,
        "topP": 0.1
    }

    response = bedrock_runtime.converse(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        messages=messages,
        system=system,
        inferenceConfig=inf_params
    )

    reply = response["output"]["message"]["content"][0]["text"].strip().lower()
    return "Yes" if reply.startswith("yes") else "No"

# sync knolwedge base
def sync_knowledge_base(knowledge_base_id, data_source_id):
    # Create Bedrock Agent client
    bedrock_agent = boto3.client('bedrock-agent')
    
    try:
        # Start the ingestion job
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id
        )
        
        ingestion_job_id = response['ingestionJob']['ingestionJobId']
        
        # Poll for job completion
        while True:
            status_response = bedrock_agent.get_ingestion_job(
                knowledgeBaseId=knowledge_base_id,
                dataSourceId=data_source_id,
                ingestionJobId=ingestion_job_id
            )
            
            status = status_response['ingestionJob']['status']
            
            if status == 'COMPLETE':
                print("Data sync completed successfully")
                break
            elif status in ['FAILED', 'STOPPED']:
                print(f"Data sync failed with status: {status}")
                if 'errorMessage' in status_response['ingestionJob']:
                    print(f"Error: {status_response['ingestionJob']['errorMessage']}")
                break
                
            print(f"Sync info between agents in progress... Current status: {status}")
            time.sleep(5)  # Wait for 30 seconds before checking again
            
    except Exception as e:
        print(f"Error during sync: {str(e)}")

def chat_with_agent(agent_id, alias_id, region='us-east-1', prompt_override = None):
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    session_id = str(uuid.uuid4())

    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if not st.session_state.chat_history:
        st.chat_message("assistant").markdown("💬 Hi, I am MigrationPro Agent and I can help you build a migration plan based on your config files. Type [ I need help with migration ] to begin:")

    while True: 
        if prompt := st.chat_input("You:"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.chat_message("user").markdown(prompt)

            if prompt.lower() in ["exit", "quit"]:
                st.chat_message("assistant").markdown("👋 Ending session.")
                return "end"

        try:
            response = client.invoke_agent(
                agentId=agent_id,
                agentAliasId=alias_id,
                sessionId=session_id,
                inputText=prompt
            )

            agent_response = ""
            for chunk in response.get('completion', []):             
                if isinstance(chunk, dict):
                    if 'chunk' in chunk:
                        content = chunk['chunk'].get('bytes', '').decode("utf-8")
                        agent_response += content

                        st.session_state.chat_history.append({"role": "assistant", "content": agent_response})
                        st.chat_message("assistant").markdown(agent_response)

                        # determine signal to switch agent
                        if agent_id == "3SZXST6KPE" and is_file_upload_complete(content) == "Yes":
                            st.session_state.chat_history.append({"role": "✅LOG", "content": "Detected file upload is complete. I will move on to config file validation."})
                            return "to_info_validation"
                        if agent_id == "ATTGGAKZKM" and is_config_complete(content) == "Yes":
                            st.session_state.chat_history.append({"role": "✅LOG", "content": "Detected config file review is complete. I will move on to analysis the content for making a migration plan."})
                            return "to_analysis"
            # Only override the first message
            if prompt_override:
                prompt_override = None

        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.error(f"❌ Error Type: {type(e)}")
            break

    return "end"

def migration_pro_page():
    st.title("MigrationPro")
    st.write("This tool helps you plan your migration to AWS by analyzing your current infrastructure, providing recommendations, and estimating costs. Start by describing your current infrastructure below, optionally upload any architecture diagrams, and the tool will provide a detailed migration plan.")
   
    isv_col, customer_col = st.columns(2)
    
    with isv_col:
        st.subheader("Upload ISV Files")
        s3_bucket_name_isv = 'migration.test19'
        uploaded_file_isv = st.file_uploader("Choose ISV Config file", type=["json"], key="isv_config_uploader")
        if uploaded_file_isv is not None:
            if st.button('Upload ISV Config'):
                with st.spinner("Uploading ISV Config to S3..."):
                    file_name = "master_config"
                    if upload_to_s3(uploaded_file_isv, s3_bucket_name_isv, file_name):
                        st.success(f"ISV file {file_name} uploaded successfully!")
                    else:
                        st.error("Failed to upload ISV file to S3.")
            else:
                st.info(f"ISV file {file_name} selected. Click to upload.")
        
    with customer_col:
        st.subheader("Upload Customer Files")
        s3_bucket_name_customer = 'customer-config-file-v1'
        uploaded_file_customer = st.file_uploader("Choose Customer Config file", type=["json"], key="customer_config_uploader")
        if uploaded_file_customer is not None:
            if st.button('Upload Customer Config'):
                with st.spinner("Uploading Customer Config to S3..."):
                    file_name = "customer_config"
                    if upload_to_s3(uploaded_file_customer, s3_bucket_name_customer, file_name):
                        st.success(f"Customer file {file_name} uploaded successfully!")
                    else:
                        st.error("Failed to upload Customer file to S3.")
            else:
                st.info(f"Customer file {file_name} selected. Click to upload.")

    # Chat interface
    st.header("Chat with MigrationPro Agent")
    
    if 'current_agent' not in st.session_state:
        st.session_state.current_agent = "discovery"

    if st.session_state.current_agent == "discovery":
        next_step = chat_with_agent(DISCOVERY_AGENT_ID, DISCOVERY_AGENT_ALIAS_ID)

        if next_step == "to_info_validation":
            st.session_state.current_agent = "info_validation"
            sync_knowledge_base('SOUOF3OQUP', 'GWBIH3DD0R') # master config
            next_step = chat_with_agent(INFO_VALIDATION_AGENT_ID, INFO_VALIDATION_AGENT_ALIAS, 'us-east-1', prompt_override="I have uploaded the files.")

        if next_step == "to_analysis":
            st.session_state.current_agent = "analysis"
            # sync config files with knowledge base
            sync_knowledge_base('QZHNS8O1VZ', 'H2URI0CHKM') # customer config kb
            next_step = chat_with_agent(ANALYSIS_AGENT_ID, ANALYSIS_AGENT_ALIAS, 'us-east-1', prompt_override="Help me make a migration plan")

def ecm_analysis_page():
    st.title("ECM Analysis")
    s3_bucket_name_excel = 'migration.test.excel'
    uploaded_file_excel = st.file_uploader("Choose a file", type=["csv","xlsx"], key="excel_uploader")
    
    if uploaded_file_excel is not None:
        if st.button('Upload Excel'):
            file_name = uploaded_file_excel.name
            if upload_to_s3(uploaded_file_excel, s3_bucket_name_excel, file_name):
                st.success(f"Excel file {file_name} uploaded successfully!")
                display_graph(file_name)
            else:
                st.error("Failed to upload Excel file to S3.")
        else:
            st.info(f"Excel file {uploaded_file_excel.name} selected. Click to upload.")

def main():
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ("MigrationPro", "ECM Analysis"))

    if page == "MigrationPro":
        migration_pro_page()
    elif page == "ECM Analysis":
        ecm_analysis_page()

    # Add a button to clear chat history
    if st.sidebar.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

if __name__ == "__main__":
    main()
