"""
Logs Display Component
"""

import streamlit as st


def render_logs(stats_service):
    """Render recent activity logs"""
    
    st.subheader("📝 Recent Activity")
    
    display_logs = stats_service.get_logs(15)
    
    if display_logs:
        for log_entry in display_logs:
            url = log_entry.get('url', '')
            if log_entry['status'] == 'failed':
                status_code = log_entry.get('status_code', 'N/A')
                st.error(f"**#{log_entry.get('id', 0)}** | [{log_entry['time']}] | ❌ Failed (Status: {status_code})")
                if url:
                    st.markdown(f"   🔗 [{url}]({url})")
            elif log_entry['status'] == 'success':
                response_time = log_entry.get('response_time', 0)
                st.success(f"**#{log_entry.get('id', 0)}** | [{log_entry['time']}] | ✅ OK ({response_time:.0f}ms)")
                if url:
                    st.markdown(f"   🔗 [{url}]({url})")
            elif log_entry['status'] == 'checking':
                attempt_info = f" (Attempt {log_entry.get('attempt', 1)})" if log_entry.get('attempt', 1) > 1 else ""
                st.info(f"**#{log_entry.get('id', 0)}** | [{log_entry['time']}] | 🔍 Checking{attempt_info}")
                if url:
                    st.markdown(f"   🔗 [{url}]({url})")
            elif log_entry['status'] == 'complete':
                st.success(f"**[{log_entry['time']}]** {log_entry.get('message', '')}")
            elif log_entry['status'] == 'stopped':
                st.warning(f"**[{log_entry['time']}]** {log_entry.get('message', '')}")
            elif log_entry['status'] == 'error':
                st.error(f"**[{log_entry['time']}]** {log_entry.get('message', '')}")
