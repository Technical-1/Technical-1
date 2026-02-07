<a href="https://github.com/Technical-1/Technical-1">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Technical-1/Technical-1/main/compact/dark_mode_simple.svg">
    <img alt="Jacob Kanfer's GitHub Profile README" src="https://raw.githubusercontent.com/Technical-1/Technical-1/main/compact/light_mode_simple.svg">
  </picture>
</a>

## About

A dynamic GitHub profile README that automatically updates daily with live GitHub statistics. The profile banner displays an animated ASCII art logo alongside real-time stats including commit counts, lines of code, stars, followers, and repository counts -- all fetched from the GitHub GraphQL API and rendered into SVG files.

## Features

- **Auto-Updating Stats** - GitHub Actions workflow runs daily to pull the latest commit, star, follower, LOC, and repo counts via the GitHub GraphQL API
- **Animated ASCII Art Banner** - A custom ASCII art logo rendered in SVG with a cascading pulse animation
- **Dark/Light Mode Support** - Separate SVG variants that adapt to the user's GitHub theme preference using `<picture>` and `prefers-color-scheme`
- **Compact & Full Layouts** - Two layout variants: a compact card with stats, and a full-size version with skills/technologies listed
- **Intelligent LOC Caching** - SHA-256 hash-based cache tracks per-repo commit counts so only changed repos are re-queried, minimizing API calls
- **Retry Logic** - Exponential backoff for GitHub API gateway errors (502/503/504) with up to 5 retries

## Tech Stack

- **Language**: Python 3.12
- **API**: GitHub GraphQL v4
- **CI/CD**: GitHub Actions (scheduled cron + push trigger)
- **SVG Parsing**: lxml (etree)
- **Image Processing**: Pillow (for ASCII art generation)

## Getting Started

### Prerequisites

- Python 3.12+
- A GitHub [fine-grained personal access token](https://github.com/settings/tokens?type=beta) with read access to: Followers, Starring, Watching, Commit statuses, Contents, Metadata

### Installation

```bash
git clone https://github.com/Technical-1/Technical-1.git
cd Technical-1
pip install -r cache/requirements.txt
```

### Usage

```bash
# Set required environment variables
export ACCESS_TOKEN="your_github_token"
export USER_NAME="your_github_username"

# Run the stats updater
python scripts/today.py

# Generate ASCII art from an image (utility script)
python scripts/generate_ascii.py your_image.png --width 50 --height 30 --format svg
```

## Development

```bash
# Install dependencies
pip install -r cache/requirements.txt

# Run the stats updater locally
ACCESS_TOKEN=ghp_xxx USER_NAME=Technical-1 python scripts/today.py
```

## Project Structure

```
Technical-1/
├── .github/
│   └── workflows/
│       └── build.yaml          # GitHub Actions workflow (daily cron + push)
├── cache/
│   ├── requirements.txt        # Python dependencies
│   └── *.txt                   # Per-user LOC cache files (SHA-256 named)
├── compact/
│   ├── dark_mode_simple.svg    # Compact banner (dark theme)
│   └── light_mode_simple.svg   # Compact banner (light theme)
├── full/
│   ├── dark_mode.svg           # Full banner with skills (dark theme)
│   └── light_mode.svg          # Full banner with skills (light theme)
├── scripts/
│   ├── today.py                # Main stats fetcher & SVG updater
│   └── generate_ascii.py       # Image-to-ASCII art converter
├── ascii_logo.svg              # Standalone animated ASCII logo
└── README.md
```

## Technologies I've been learning and using

**Languages:**

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)
![Java](https://img.shields.io/badge/Java-ED8B00?style=for-the-badge&logo=openjdk&logoColor=white)
![C++](https://img.shields.io/badge/C++-00599C?style=for-the-badge&logo=cplusplus&logoColor=white)
![C](https://img.shields.io/badge/C-A8B9CC?style=for-the-badge&logo=c&logoColor=black)
![Rust](https://img.shields.io/badge/Rust-000000?style=for-the-badge&logo=rust&logoColor=white)
![Go](https://img.shields.io/badge/Go-00ADD8?style=for-the-badge&logo=go&logoColor=white)
![Swift](https://img.shields.io/badge/Swift-FA7343?style=for-the-badge&logo=swift&logoColor=white)
![R](https://img.shields.io/badge/R-276DC3?style=for-the-badge&logo=r&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-4479A1?style=for-the-badge&logo=postgresql&logoColor=white)

**Cloud & Data:**

![Firebase](https://img.shields.io/badge/Firebase-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)
![AWS](https://img.shields.io/badge/AWS-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)
![Google Cloud](https://img.shields.io/badge/Google_Cloud-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)
![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=for-the-badge&logo=snowflake&logoColor=white)
![Databricks](https://img.shields.io/badge/Databricks-FF3621?style=for-the-badge&logo=databricks&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)

**Automation & Enterprise:**

![Puppeteer](https://img.shields.io/badge/Puppeteer-40B5A4?style=for-the-badge&logo=puppeteer&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![Power BI](https://img.shields.io/badge/Power%20BI-F2C811?style=for-the-badge&logoColor=black)
![ServiceNow](https://img.shields.io/badge/ServiceNow-93C90E?style=for-the-badge&logoColor=white)
![Chrome Extension API](https://img.shields.io/badge/Chrome_Extensions-4285F4?style=for-the-badge&logo=google-chrome&logoColor=white)
![Electron](https://img.shields.io/badge/Electron-47848F?style=for-the-badge&logo=electron&logoColor=white)

**Web Development:**

![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Vue.js](https://img.shields.io/badge/Vue.js-4FC08D?style=for-the-badge&logo=vuedotjs&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)
![Express.js](https://img.shields.io/badge/Express.js-000000?style=for-the-badge&logo=express&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)

**AI & Machine Learning:**

![TensorFlow](https://img.shields.io/badge/TensorFlow-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Jupyter](https://img.shields.io/badge/Jupyter-F37626?style=for-the-badge&logo=jupyter&logoColor=white)

**DevOps & Tools:**

![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)
![VS Code](https://img.shields.io/badge/VS_Code-007ACC?style=for-the-badge&logo=visual-studio-code&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![Postman](https://img.shields.io/badge/Postman-FF6C37?style=for-the-badge&logo=postman&logoColor=white)

---

**Connect:**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/jacob-kanfer)
[![Website](https://img.shields.io/badge/Website-000000?style=for-the-badge&logo=About.me&logoColor=white)](https://jacobkanfer.com)
[![Email](https://img.shields.io/badge/Email-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:jacobkanfer8@gmail.com)

## Author

Jacob Kanfer - [GitHub](https://github.com/Technical-1)
