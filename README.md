# 🔍 URL Checker - Turing ES

Automated URL validation system for Turing ES using Selenium for real browser navigation, avoiding anti-bot blocks.

## 📋 Features

- ✅ Real browser navigation via Selenium (Chrome/Chromium)
- ✅ **Parallel execution with 2-5 simultaneous browsers** (configurable)
- ✅ **Web interface with Streamlit** for visual configuration and real-time monitoring
- ✅ Command-line interface (CLI) for automation
- ✅ Smart retry system (up to 3 attempts per URL)
- ✅ Automatic API pagination
- ✅ Reports in TXT and JSON formats
- ✅ Automatic email sending via Mailchimp Transactional
- ✅ Performance optimizations (disables images/CSS/JS)
- ✅ Configuration via INI file or environment variables
- ✅ Detailed logging
- ✅ Multi-platform support (Windows/Linux/Mac)

## 🚀 Installation and Execution

### Prerequisites

- Python 3.8 or higher
- Google Chrome or Chromium installed
- Internet connection

### Quick Start

#### Option 1: Web Interface (Recommended)

Visual interface with real-time monitoring:

**Windows (PowerShell):**
```powershell
.\run-web.bat
```

**Linux/Mac:**
```bash
chmod +x run-web.sh
./run-web.sh
```

Then open your browser at: **http://localhost:8501**

#### Option 2: Command Line Interface

Automated execution for scripts:

**Windows (PowerShell):**
```powershell
.\run.bat
```

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

**What the scripts do:**
- ✓ Check Python version
- ✓ Create virtual environment (venv)
- ✓ Install dependencies
- ✓ Run the program

### Manual Installation

If you prefer manual installation:

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python main.py
```

## ⚙️ Configuration

### config.ini File

The `config.ini` file contains all system settings:

```ini
[API]
base_url = http://localhost:2700/api/sn/sample/search
locale = en

[EMAIL]
recipient = your-email@gmail.com
sender_email = noreply@example.com
sender_name = URL Checker - Turing

[MAILCHIMP]
# Get your key at: https://mandrillapp.com/settings
api_key = your-api-key-here

[SELENIUM]
page_load_timeout = 15
element_wait_timeout = 10
headless = false

[RETRY]
max_attempts = 3
retry_delay = 2

[PERFORMANCE]
page_delay = 0.5
url_check_delay = 0.3
disable_images = true
parallel_browsers = 3  # 1-5 simultaneous browsers (1 = sequential)

[REPORT]
output_dir = reports
max_urls_in_email = 50
```

### Key Configuration Parameters

#### Parallel Execution

The system supports parallel URL checking with multiple simultaneous browsers:

- **`parallel_browsers = 1`**: Sequential mode (original behavior)
- **`parallel_browsers = 2-5`**: Parallel mode with N simultaneous Chrome instances
- **Recommended**: `3` browsers for balanced performance
- **Console Output**: Shows "⚡ Parallel mode: N simultaneous browsers"

**Performance Tips:**
- More browsers = faster checking but higher CPU/memory usage
- Start with 3 browsers and adjust based on your system resources
- Sequential mode (1 browser) is more stable but slower

#### Other Settings

### Environment Variables

You can use environment variables to override `config.ini` settings:

```bash
# Windows (PowerShell):
$env:MAILCHIMP_API_KEY="your-key-here"
$env:EMAIL_RECIPIENT="your-email@gmail.com"

# Linux/Mac:
export MAILCHIMP_API_KEY="your-key-here"
export EMAIL_RECIPIENT="your-email@gmail.com"
```

**Variable format:** `SECTION_KEY` (e.g., `MAILCHIMP_API_KEY`, `EMAIL_RECIPIENT`)

### Mailchimp Configuration

To send emails, you need to configure Mailchimp Transactional (Mandrill):

1. Access: https://mandrillapp.com/
2. Create account or login
3. Go to **Settings** → **API Keys**
4. Copy your API Key
5. Configure in `config.ini` or via environment variable

## 📖 Usage

### Web Interface

Start the Streamlit application:

```bash
# Windows
.\run-web.bat

# Linux/Mac
./run-web.sh
```

The web interface will automatically open in your browser at **http://localhost:8501**

#### Web Interface Features

**📊 Dashboard Metrics (4-column layout):**
- **Total URLs Checked**: Shows current/total URLs (e.g., 150/500)
- **Failed URLs**: Real-time count of problematic URLs
- **Requests/s**: Current processing speed
- **Est. Time Remaining**: Dynamic time estimate to completion

**📈 Real-time Performance Chart:**
- Response time tracking for each URL check
- Moving average trend line (10-request window)
- Live updates as URLs are being checked
- Visual performance monitoring

**📝 Recent Activity Log (Last 15 entries):**
- Sequential ID tracking (e.g., #123, #124, #125)
- Timestamp for each check (HH:MM:SS format)
- Status indicators:
  - ✅ **OK**: Successful check with response time (e.g., "850ms")
  - ❌ **Failed**: Error with HTTP status code (e.g., "Status: 404")
  - 🔍 **Checking**: Currently in progress with attempt number
- Full URL display
- FIFO order (most recent first)
- Smooth scrolling with no jumping items

**🎛️ Visual Configuration Panel:**
- **Base URL Selection**: Choose from multiple configured endpoints
- **Parallel Execution**: Slider to set 1-5 simultaneous browsers
- **Timeout Settings**: Adjust page load and element wait times
- **Delays Configuration**: Set delays between pages and URL checks
- **Retry Settings**: Configure max attempts and retry delay
- **Performance Options**: Toggle image loading, CSS, and JavaScript
- **Email Settings**: Configure recipient and sender details
- **Real-time Validation**: All settings validated before starting

**⏯️ Execution Control:**
- **Start Button**: Begin URL checking with current configuration
- **Stop Button**: Gracefully stop the checking process anytime
- **Progress Bar**: Visual progress indicator with percentage and elapsed time
- **Status Messages**: Real-time feedback on execution state

**📧 Automatic Email Notifications:**
- Sends report automatically when check completes with failures
- Visual confirmation when email is sent
- Warning messages if email configuration is missing
- Error handling with clear feedback messages

**💾 Results Export:**
- Download failed URLs as JSON file
- Includes complete metadata for each failure
- Ready for further processing or analysis

**🔄 Live Updates:**
- Batch processing: Handles up to 10 updates per refresh cycle
- Optimized refresh rate (50ms) for smooth real-time experience
- No duplicate counting: Each failed URL counted once (even with retries)
- Consistent display: All metrics update simultaneously

### Command Line Interface

For automation and scripts:

```bash
python main.py
```

**CLI Options:**

```bash
# Verbose mode (detailed logs)
python main.py --verbose

# Headless mode (no browser window)
python main.py --headless

# Don't send email
python main.py --no-email

# Use custom configuration file
python main.py --config my-config.ini

# Combine options
python main.py --verbose --headless --no-email
```

## 📂 Project Structure

```
url-checker/
├── main.py                 # CLI entry point
├── app.py                  # Streamlit web interface
├── config.ini             # Configuration
├── requirements.txt       # Python dependencies
├── run.bat               # Windows CLI execution
├── run.sh                # Linux/Mac CLI execution
├── run-web.bat           # Windows web interface
├── run-web.sh            # Linux/Mac web interface
├── README.md             # This documentation
├── .gitignore            # Git ignored files
├── .env.example          # Environment variables example
├── src/                  # Source code
│   ├── __init__.py
│   ├── checker.py        # Main URLChecker class
│   ├── config_loader.py  # Configuration manager
│   ├── report_generator.py  # Report generator
│   └── email_sender.py   # Email sending
├── reports/              # Generated reports (TXT/JSON)
└── logs/                 # Log files
```

## 📊 Reports

The system generates two types of reports:

### TXT Report
- Human-readable format
- Includes date, time, and summary
- Lists all problematic URLs

**Example:**
```
================================================================================
URL VALIDATION REPORT
================================================================================
Date: 01/15/2024 14:30:00
Total problematic URLs: 5
================================================================================

URL: https://example.com/page1
Status Code: 404
API Page: 3
Attempts: 3
--------------------------------------------------------------------------------
...
```

### JSON Report
- Structured format for automated processing
- Includes complete metadata
- Easy integration with other tools

**Example:**
```json
{
  "timestamp": "2024-01-15T14:30:00",
  "total_failed": 5,
  "failed_urls": [
    {
      "url": "https://example.com/page1",
      "status_code": 404,
      "page": 3,
      "attempts": 3
    }
  ]
}
```

## 📧 Automatic Email

When problematic URLs are found, the system automatically sends an email containing:

- **Summary:** Total problematic URLs
- **URL List:** Up to 50 URLs in email body
- **Attachments:** Complete reports (TXT and JSON)
- **HTML Formatting:** Styled and easy-to-read email

**Email is NOT sent if:**
- No problematic URLs found
- Mailchimp API Key not configured
- `--no-email` option used

## 🔧 Customization

### Adjust Timeouts

In `config.ini`:
```ini
[SELENIUM]
page_load_timeout = 20  # Increase if pages take long to load
element_wait_timeout = 15

[RETRY]
max_attempts = 5  # More attempts for unstable sites
retry_delay = 3  # More time between attempts
```

### Performance

To speed up verification:
```ini
[PERFORMANCE]
page_delay = 0.2  # Reduce delay between pages
url_check_delay = 0.1  # Reduce delay between URLs
disable_images = true  # Keep disabled
parallel_browsers = 5  # Maximum parallelization (use with caution)
```

For slow connections or resource-constrained systems:
```ini
[PERFORMANCE]
page_delay = 1.0  # Increase delay
url_check_delay = 0.5
parallel_browsers = 1  # Sequential mode (most stable)
```

**Note:** Parallel execution with multiple browsers significantly speeds up checking but increases CPU and memory usage. Monitor your system resources and adjust accordingly.

### Headless Mode

To run without graphical interface (servers):
```ini
[SELENIUM]
headless = true
```

Or via command line:
```bash
python main.py --headless
```

## 🐛 Troubleshooting

### Error: "Chrome/Chromium not found"

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install chromium-browser chromium-chromedriver

# Fedora/RHEL
sudo dnf install chromium chromium-chromedriver
```

**Windows/Mac:** Install Google Chrome from official website

### Error: "ModuleNotFoundError"

Make sure virtual environment is activated and dependencies installed:
```bash
pip install -r requirements.txt
```

### Email not being sent

Check:
1. ✓ Mailchimp API Key configured
2. ✓ Recipient email configured
3. ✓ `mailchimp-transactional` library installed
4. ✓ Problematic URLs were found
5. ✓ `--no-email` option not used

### Pages taking too long

Reduce timeouts in `config.ini`:
```ini
[SELENIUM]
page_load_timeout = 10
element_wait_timeout = 5
```

## 📝 Logs

Logs are saved in `logs/url_checker_YYYYMMDD.log`:

- **INFO:** Normal operations
- **WARNING:** Non-critical issues
- **ERROR:** Errors needing attention

Use `--verbose` for more detailed logs:
```bash
python main.py --verbose
```

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork the project
2. Create a branch for your feature (`git checkout -b feature/MyFeature`)
3. Commit your changes (`git commit -m 'Add MyFeature'`)
4. Push to the branch (`git push origin feature/MyFeature`)
5. Open a Pull Request

## 📄 License

This project is under the MIT license. See the `LICENSE` file for more details.

---

**Version:** 2025.4 
**Last update:** December 2025
