"""
Stats Service - Manages statistics and metrics calculation
"""

import time


class StatsService:
    """Service for managing statistics and metrics"""
    
    def __init__(self):
        self.stats = {
            'total_checked': 0,
            'total_failed': 0,
            'current_page': 0,
            'total_pages': 0,
            'total_urls': 0,
            'start_time': None,
            'estimated_time': None
        }
        self.log_history = []
        self.response_times = []
        self.results = []
    
    def reset(self):
        """Reset all statistics"""
        self.stats = {
            'total_checked': 0,
            'total_failed': 0,
            'current_page': 0,
            'total_pages': 0,
            'total_urls': 0,
            'start_time': time.time(),
            'estimated_time': None
        }
        self.log_history = []
        self.response_times = []
        self.results = []
    
    def update_page(self, page, total_pages, total_urls):
        """Update page statistics"""
        self.stats['current_page'] = page
        self.stats['total_pages'] = total_pages
        self.stats['total_urls'] = total_urls
        self._calculate_eta()
    
    def add_result(self, url, status, page, attempts, response_time, timestamp):
        """Add a check result"""
        self.stats['total_checked'] += 1
        
        # Store response time for chart
        if response_time:
            response_time_ms = response_time * 1000
            self.response_times.append(response_time_ms)
            # Keep only last 100 entries
            if len(self.response_times) > 100:
                self.response_times = self.response_times[-100:]
        
        # Count failures
        if status != 200:
            self.stats['total_failed'] += 1
            self.results.append({
                'url': url,
                'status': status,
                'page': page,
                'attempts': attempts,
                'timestamp': timestamp
            })
            
            # Add failed log entry
            self._add_log({
                'id': self.stats['total_checked'],
                'time': timestamp.strftime('%H:%M:%S'),
                'status': 'failed',
                'status_code': status,
                'url': url,
                'response_time': 0
            })
        else:
            # Add success log entry
            response_time_ms = response_time * 1000 if response_time else 0
            self._add_log({
                'id': self.stats['total_checked'],
                'time': timestamp.strftime('%H:%M:%S'),
                'status': 'success',
                'status_code': 200,
                'url': url,
                'response_time': response_time_ms
            })
    
    def add_checking_log(self, url, page, attempt, timestamp):
        """Add checking log entry"""
        self._add_log({
            'id': self.stats['total_checked'] + 1,
            'time': timestamp.strftime('%H:%M:%S'),
            'status': 'checking',
            'url': url,
            'attempt': attempt
        })
    
    def add_system_log(self, status, message, timestamp):
        """Add system log entry (complete/stopped/error)"""
        self._add_log({
            'time': timestamp.strftime('%H:%M:%S'),
            'status': status,
            'message': message,
            'url': ''
        })
    
    def _add_log(self, log_entry):
        """Internal method to add log entry"""
        self.log_history.append(log_entry)
        # Keep only last 50 entries (FIFO)
        if len(self.log_history) > 50:
            self.log_history = self.log_history[-50:]
    
    def _calculate_eta(self):
        """Calculate estimated time remaining"""
        if self.stats['total_checked'] > 0 and self.stats['start_time']:
            elapsed = time.time() - self.stats['start_time']
            rate = self.stats['total_checked'] / elapsed
            remaining = self.stats['total_urls'] - self.stats['total_checked']
            if rate > 0:
                eta_seconds = remaining / rate
                self.stats['estimated_time'] = self._format_time(eta_seconds)
    
    def _format_time(self, seconds):
        """Format seconds into readable time string"""
        if seconds >= 3600:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
        elif seconds >= 120:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            return f"{int(seconds)}s"
    
    def get_requests_per_second(self):
        """Calculate current requests per second"""
        if self.stats['total_checked'] > 0 and self.stats['start_time']:
            elapsed = time.time() - self.stats['start_time']
            if elapsed > 0:
                return self.stats['total_checked'] / elapsed
        return 0.0
    
    def get_elapsed_time(self):
        """Get elapsed time formatted"""
        if self.stats['start_time']:
            elapsed = time.time() - self.stats['start_time']
            return self._format_time(elapsed)
        return "0s"
    
    def get_progress(self):
        """Get progress percentage"""
        if self.stats['total_urls'] > 0:
            return self.stats['total_checked'] / self.stats['total_urls']
        return 0.0
    
    def get_stats(self):
        """Get current statistics"""
        return self.stats.copy()
    
    def get_logs(self, count=15):
        """Get recent log entries"""
        return list(reversed(self.log_history[-count:]))
    
    def get_response_times(self):
        """Get response times data"""
        return self.response_times.copy()
    
    def get_results(self):
        """Get failed results"""
        return self.results.copy()
