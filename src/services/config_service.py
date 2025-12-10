"""
Configuration Service - Handles all configuration loading and management
"""

from ..config_loader import ConfigLoader


class ConfigService:
    """Service for managing application configuration"""
    
    def __init__(self):
        self.config_loader = ConfigLoader()
        self._cached_config = None
    
    def load_config(self):
        """Load and return complete configuration"""
        # Reload config file to pick up any changes
        self.config_loader.config.read(self.config_loader.config_file, encoding='utf-8')
        
        # Clear cache to force reload
        self._cached_config = None
        
        if self._cached_config:
            return self._cached_config
        
        try:
            # Load base URLs with format: base_url.ID = "Name";URL
            base_urls = {}
            default_base_url = None
            
            # Try to load all base_url.N entries
            for i in range(1, 100):  # Support up to 99 URLs
                key = f'base_url.{i}'
                try:
                    value = self.config_loader.config.get('API', key)
                    if value:
                        # Parse format: Name;URL
                        if ';' in value:
                            parts = value.split(';', 1)
                            name = parts[0].strip()
                            url = parts[1].strip()
                            
                            if name and url:
                                base_urls[name] = url
                                
                                # First URL is default
                                if default_base_url is None:
                                    default_base_url = url
                except:
                    # Silently skip non-existent keys
                    break  # Stop when we hit the first missing key
            
            # Fallback if no base_url.N found
            if not base_urls:
                try:
                    default_base_url = self.config_loader.get('API', 'base_url', 
                        'http://localhost:2700/api/sn/sample/search')
                    base_urls['Default'] = default_base_url
                except:
                    default_base_url = 'http://localhost:2700/api/sn/sample/search'
                    base_urls['Default'] = default_base_url
            
            # Read error_status_codes as list of integers
            error_codes_str = self.config_loader.get('PERFORMANCE', 'error_status_codes', '404')
            error_status_codes = [int(code.strip()) for code in error_codes_str.split(',') if code.strip().isdigit()]
            if not error_status_codes:
                error_status_codes = [404]  # Default to 404 if invalid
            
            # Read resume_from_checkpoint
            resume_from_checkpoint = self.config_loader.get_bool('PERFORMANCE', 'resume_from_checkpoint', True)
            
            self._cached_config = {
                'base_urls': base_urls,
                'default_base_url': default_base_url,
                'locale': self.config_loader.get('API', 'locale', 'pt'),
                'page_load_timeout': self.config_loader.get_int('SELENIUM', 'page_load_timeout', 15),
                'element_wait_timeout': self.config_loader.get_int('SELENIUM', 'element_wait_timeout', 10),
                'headless': self.config_loader.get_bool('SELENIUM', 'headless', False),
                'max_attempts': self.config_loader.get_int('RETRY', 'max_attempts', 3),
                'retry_delay': self.config_loader.get_float('RETRY', 'retry_delay', 2),
                'page_delay': self.config_loader.get_float('PERFORMANCE', 'page_delay', 0.5),
                'url_check_delay': self.config_loader.get_float('PERFORMANCE', 'url_check_delay', 0.3),
                'disable_images': self.config_loader.get_bool('PERFORMANCE', 'disable_images', True),
                'parallel_browsers': self.config_loader.get_int('PERFORMANCE', 'parallel_browsers', 3),
                'error_status_codes': error_status_codes,
                'resume_from_checkpoint': resume_from_checkpoint,
                'email': {
                    'recipient': self.config_loader.get('EMAIL', 'recipient', ''),
                    'sender_email': self.config_loader.get('EMAIL', 'sender_email', 'noreply@example.com'),
                    'sender_name': self.config_loader.get('EMAIL', 'sender_name', 'URL Checker - Turing')
                },
                'brevo': {
                    'api_key': self.config_loader.get('BREVO', 'api_key', '')
                }
            }
        except Exception as e:
            # Fallback default configuration
            default_base_url = 'http://localhost:2700/api/sn/sample/search'
            self._cached_config = {
                'base_urls': {'Default': default_base_url},
                'default_base_url': default_base_url,
                'locale': 'pt',
                'page_load_timeout': 15,
                'element_wait_timeout': 10,
                'headless': False,
                'max_attempts': 3,
                'retry_delay': 2.0,
                'page_delay': 0.5,
                'url_check_delay': 0.3,
                'disable_images': True,
                'parallel_browsers': 3,
                'error_status_codes': [404],
                'resume_from_checkpoint': True,
                'email': {
                    'recipient': '',
                    'sender_email': 'noreply@example.com',
                    'sender_name': 'URL Checker - Turing'
                },
                'brevo': {
                    'api_key': ''
                }
            }
        
        return self._cached_config
    
    def get_default_config(self):
        """Get default configuration values"""
        return self.load_config()
    
    def build_runtime_config(self, **overrides):
        """Build runtime configuration with overrides"""
        base_config = self.load_config()
        
        # Merge overrides
        runtime_config = base_config.copy()
        runtime_config.update(overrides)
        
        return runtime_config
