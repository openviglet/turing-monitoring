"""
Configuration Sidebar Component
"""

import streamlit as st
from ..services import ConfigService


def render_config_sidebar():
    """Render configuration sidebar and return selected config"""
    
    config_service = ConfigService()
    default_config = config_service.get_default_config()
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.subheader("API Settings")
        
        # Use URLs from config.ini (base_url.1, base_url.2, etc.)
        predefined_urls = default_config['base_urls']
        
        # URL selection
        url_options = list(predefined_urls.keys())
        
        # Find default selection
        default_index = 0
        for i, (name, url) in enumerate(predefined_urls.items()):
            if url == default_config['default_base_url']:
                default_index = i
                break
        
        # Disable all inputs when running
        is_running = st.session_state.get('running', False)
        
        selected_option = st.selectbox(
            "Select Base URL",
            url_options,
            index=default_index,
            disabled=is_running
        )
        
        # Get selected URL
        base_url = predefined_urls[selected_option]
        st.text_input("Selected URL", base_url, disabled=True)
        
        locale = st.text_input("Locale", default_config['locale'], disabled=is_running)
        
        st.subheader("Performance")
        col1, col2 = st.columns(2)
        with col1:
            parallel_browsers = st.slider("Parallel Browsers", 1, 5, default_config['parallel_browsers'], disabled=is_running)
        with col2:
            headless = st.checkbox("Headless Mode", default_config['headless'], disabled=is_running)
        
        page_delay = st.slider("Page Delay (s)", 0.1, 2.0, default_config['page_delay'], 0.1, disabled=is_running)
        url_check_delay = st.slider("URL Check Delay (s)", 0.1, 1.0, default_config['url_check_delay'], 0.1, disabled=is_running)
        
        st.subheader("Retry Settings")
        max_attempts = st.slider("Max Attempts", 1, 5, default_config['max_attempts'], disabled=is_running)
        retry_delay = st.slider("Retry Delay (s)", 1.0, 5.0, default_config['retry_delay'], 0.5, disabled=is_running)
        
        st.subheader("Timeouts")
        page_load_timeout = st.slider("Page Load Timeout (s)", 5, 30, default_config['page_load_timeout'], disabled=is_running)
        element_wait_timeout = st.slider("Element Wait Timeout (s)", 5, 20, default_config['element_wait_timeout'], disabled=is_running)
        
        disable_images = st.checkbox("Disable Images/CSS", default_config['disable_images'], disabled=is_running)
    
    return {
        'base_url': base_url,
        'locale': locale,
        'page_load_timeout': page_load_timeout,
        'element_wait_timeout': element_wait_timeout,
        'headless': headless,
        'max_attempts': max_attempts,
        'retry_delay': retry_delay,
        'page_delay': page_delay,
        'url_check_delay': url_check_delay,
        'disable_images': disable_images,
        'parallel_browsers': parallel_browsers,
        'error_status_codes': default_config['error_status_codes'],
        'resume_from_checkpoint': default_config['resume_from_checkpoint'],
        'email': default_config['email'],
        'brevo': default_config['brevo']
    }
