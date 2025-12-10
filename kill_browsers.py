"""
Utility script to kill all Chrome/ChromeDriver processes launched by Selenium
Run this if browsers are stuck or consuming resources
"""

import psutil
import time


def kill_selenium_browsers():
    """Kill all Chrome and ChromeDriver processes"""
    killed_count = 0
    
    print("\n" + "=" * 80)
    print("KILLING SELENIUM BROWSER PROCESSES")
    print("=" * 80)
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_name = proc.info['name'].lower() if proc.info['name'] else ''
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                
                # Check if it's a Chrome/ChromeDriver process
                is_selenium_chrome = False
                
                # ChromeDriver processes
                if 'chromedriver' in proc_name:
                    is_selenium_chrome = True
                    print(f"\n🔍 Found ChromeDriver:")
                    print(f"   PID: {proc.info['pid']}")
                    print(f"   Name: {proc.info['name']}")
                
                # Chrome processes with automation flags
                elif 'chrome' in proc_name:
                    automation_flags = [
                        '--remote-debugging',
                        '--test-type',
                        '--enable-automation',
                        '--disable-blink-features=automationcontrolled',
                        '--headless'
                    ]
                    
                    for flag in automation_flags:
                        if flag in cmdline.lower():
                            is_selenium_chrome = True
                            print(f"\n🔍 Found Selenium Chrome:")
                            print(f"   PID: {proc.info['pid']}")
                            print(f"   Name: {proc.info['name']}")
                            print(f"   Flag: {flag}")
                            break
                
                if is_selenium_chrome:
                    proc.kill()
                    killed_count += 1
                    print(f"   ✅ Killed successfully")
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                pass
        
        print("\n" + "=" * 80)
        if killed_count > 0:
            print(f"✅ Successfully killed {killed_count} browser process(es)")
            print("Waiting 2 seconds for cleanup...")
            time.sleep(2)
        else:
            print("✅ No Selenium browser processes found")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    kill_selenium_browsers()
