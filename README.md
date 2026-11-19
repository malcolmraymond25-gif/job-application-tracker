# Job Application Tracker

A Flask and MySQL web application for organizing companies, job listings, contacts, and job applications. It includes a dashboard and a skill-based Job Match feature.

## Features

- Create, view, edit, and delete companies, jobs, applications, and contacts
- View dashboard counts and recent applications
- Compare entered skills with job requirements and rank jobs by match percentage
- Store job requirements and interview notes as JSON in MySQL

## Technologies

- Python 3
- Flask
- MySQL
- HTML and CSS
- MySQL Connector/Python

## Requirements

Install these before starting:

- Python 3
- MySQL Server and MySQL Workbench
- PyCharm is recommended for development

## Setup

### 1. Clone the repository

Use GitHub Desktop to clone the repository, then open the project folder in PyCharm.

### 2. Create and activate a virtual environment

In PyCharm, configure a project virtual environment named `.venv`. Open PyCharm’s Terminal and install the dependencies:

```bash
python -m pip install -r requirements.txt