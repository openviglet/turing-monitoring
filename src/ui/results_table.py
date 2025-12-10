"""
Results Table Component
"""

import streamlit as st
import json
from datetime import datetime


def render_results_table(stats_service):
    """Render failed URLs results table"""
    
    results = stats_service.get_results()
    
    if results:
        st.divider()
        st.subheader("❌ Failed URLs")
        
        # Display as expandable items with clickable links
        for idx, result in enumerate(results, 1):
            # Handle missing fields with defaults
            status = result.get('status', 'Unknown')
            page = result.get('page', 'N/A')
            url = result.get('url', 'N/A')
            attempts = result.get('attempts', 0)
            timestamp = result.get('timestamp')
            
            # Format timestamp safely - handle both datetime objects and strings
            if timestamp:
                if isinstance(timestamp, str):
                    time_str = timestamp
                else:
                    try:
                        time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        time_str = str(timestamp)
            else:
                time_str = 'N/A'
            
            with st.expander(f"#{idx} - Status {status} - Page {page}"):
                st.markdown(f"**URL:** [{url}]({url})")
                st.markdown(f"**Status Code:** {status}")
                st.markdown(f"**Page:** {page}")
                st.markdown(f"**Attempts:** {attempts}")
                st.markdown(f"**Time:** {time_str}")
        
        # Download button
        json_data = json.dumps(results, indent=2, default=str)
        st.download_button(
            label="📥 Download Failed URLs (JSON)",
            data=json_data,
            file_name=f"failed_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
