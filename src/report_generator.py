"""
Report Generator - Creates TXT and JSON reports
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Tuple


class ReportGenerator:
    """Report generator for URL validation results"""
    
    def __init__(self, output_dir: str = 'reports'):
        """
        Initialize report generator
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def generate(self, failed_urls: List[Dict]) -> Tuple[str, str]:
        """
        Generate TXT and JSON reports
        
        Args:
            failed_urls: List of URLs that failed validation
            
        Returns:
            Tuple with (txt_report_path, json_report_path)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_report = os.path.join(self.output_dir, f"url_check_report_{timestamp}.txt")
        json_report = os.path.join(self.output_dir, f"url_check_report_{timestamp}.json")
        
        self._generate_txt_report(failed_urls, txt_report)
        self._generate_json_report(failed_urls, json_report)
        
        return txt_report, json_report
    
    def _generate_txt_report(self, failed_urls: List[Dict], filename: str):
        """Generate text report"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("URL VALIDATION REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Date: {datetime.now().strftime('%m/%d/%Y %H:%M:%S')}\n")
            f.write(f"Total problematic URLs: {len(failed_urls)}\n")
            f.write("=" * 80 + "\n\n")
            
            if failed_urls:
                for item in failed_urls:
                    f.write(f"URL: {item['url']}\n")
                    f.write(f"Status Code: {item['status_code']}\n")
                    f.write(f"API Page: {item['page']}\n")
                    f.write(f"Attempts: {item.get('attempts', 1)}\n")
                    if 'error' in item:
                        f.write(f"Error: {item['error']}\n")
                    f.write("-" * 80 + "\n")
            else:
                f.write("No problematic URLs found! ✓\n")
    
    def _generate_json_report(self, failed_urls: List[Dict], filename: str):
        """Generate JSON report"""
        with open(filename, 'w', encoding='utf-8') as f:
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'total_failed': len(failed_urls),
                'failed_urls': failed_urls
            }
            json.dump(report_data, f, indent=2, ensure_ascii=False)
