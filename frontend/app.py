import streamlit as st
import requests

st.title("Stock Market Streaming App")

start_streaming_url = "http://backend:8000/start-streaming/"
stop_streaming_url = "http://backend:8000/stop-streaming/"

if st.button('Start Streaming'):
    response = requests.get(start_streaming_url)
    st.write(response.json())

if st.button('Stop Streaming'):
    response = requests.get(stop_streaming_url)
    st.write(response.json())
