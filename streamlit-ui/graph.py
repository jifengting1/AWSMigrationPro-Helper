import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import boto3
import io

# AWS S3 configuration
S3_BUCKET_NAME = 'migration.test.excel'


# Initialize S3 client
s3 = boto3.client('s3')


def get_excel_data(file_name):
    try:
        # Download the file from S3
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=file_name)
        file_content = response['Body'].read()

        # Read the Excel file
        df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl', sheet_name='Summary')
        return df

    except Exception as e:
        st.sidebar.error(f"Error reading Excel file from S3: {str(e)}")
        return None

def create_radar_chart(df):
    # Assuming the first column contains categories and subsequent columns are data series
    categories = df.iloc[:, 0].tolist()
    
    fig = go.Figure()

    for column in df.columns[1:]:
        values = df[column].tolist()
        # Add the first value again to close the polygon
        values.append(values[0])
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],  # Repeat the first category to close the polygon
            mode='lines',  # Use lines mode
            name=column
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max(df.iloc[:, 1:].max())]  # Set range from 0 to max value
            )),
        showlegend=True,
        title='Radar Chart from Excel'
    )
    return fig

# Streamlit app
st.title("Excel Radar Chart Viewer")

