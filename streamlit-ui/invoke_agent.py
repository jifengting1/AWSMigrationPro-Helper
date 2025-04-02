from boto3.session import Session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import boto3
import json
import os
from requests import request
import base64
import io
import sys

import uuid

class BedrockAgentClient:
    def __init__(self, region_name="us-east-1"):
        # Initialize the Bedrock Agent Runtime client
        self.runtime_client = boto3.client(
            service_name="bedrock-agent-runtime",
            region_name=region_name
        )

    def chat_with_agent(self, agent_id, agent_alias_id, prompt):
        try:
            # Create a unique session ID for the conversation
            session_id = uuid.uuid4().hex
            
            # Invoke the agent
            response = self.runtime_client.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_id,
                inputText=prompt
            )

            # Process the streaming response
            completion = ""
            trace_data='' 
            
            for event in response['completion']:
                if 'chunk' in event:
                    # Get the response chunk
                    chunk = event['chunk']['bytes'].decode('utf-8')
                    completion+= chunk
                    
               
                return {
            "status_code": 200,
            "body": json.dumps({"trace_data": trace_data,"response": completion})
                     } 

        except Exception as e:
                return {
            "status_code": 500,
            "body": json.dumps({"error": str(e)})
                    }