"""
Metrics Display Component
"""

import streamlit as st


def render_metrics(stats_service):
    """Render metrics display (4 columns)"""
    
    stats = stats_service.get_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        url_info = f"{stats['total_checked']}"
        if stats.get('total_urls', 0) > 0:
            url_info += f" / {stats['total_urls']}"
        st.metric("Total URLs Checked", url_info)
    
    with col2:
        st.metric("Failed URLs", stats['total_failed'])
    
    with col3:
        # Calculate requests per second
        req_per_sec = stats_service.get_requests_per_second()
        if req_per_sec > 0:
            st.metric("Requests/s", f"{req_per_sec:.2f}")
        else:
            st.metric("Requests/s", "-")
    
    with col4:
        eta = stats.get('estimated_time')
        if eta:
            st.metric("Est. Time Remaining", eta)
        elif st.session_state.get('running', False):
            st.metric("Est. Time Remaining", "Calculating...")
        else:
            st.metric("Est. Time Remaining", "-")
