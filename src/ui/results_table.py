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
            with st.expander(f"#{idx} - Status {result['status']} - Page {result['page']}"):
                st.markdown(f"**URL:** [{result['url']}]({result['url']})")
                st.markdown(f"**Status Code:** {result['status']}")
                st.markdown(f"**Page:** {result['page']}")
                st.markdown(f"**Attempts:** {result['attempts']}")
                st.markdown(f"**Time:** {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Download button
        json_data = json.dumps(results, indent=2, default=str)
        st.download_button(
            label="📥 Download Failed URLs (JSON)",
            data=json_data,
            file_name=f"failed_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
