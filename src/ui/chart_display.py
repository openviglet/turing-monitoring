"""
Chart Display Component
"""

import streamlit as st
import pandas as pd


def render_chart(stats_service):
    """Render response time chart"""
    
    st.subheader("📈 Response Times (ms)")
    
    response_times = stats_service.get_response_times()
    
    if response_times:
        df = pd.DataFrame({
            'Response Time': response_times
        })
        df['Average (10 req)'] = df['Response Time'].rolling(window=min(10, len(df)), min_periods=1).mean()
        st.line_chart(df, height=200)
    else:
        # Show placeholder chart when no data yet
        placeholder_df = pd.DataFrame({
            'Response Time': [0, 0],
            'Average (10 req)': [0, 0]
        })
        st.line_chart(placeholder_df, height=200)
        st.caption("⏳ Waiting for data...")
